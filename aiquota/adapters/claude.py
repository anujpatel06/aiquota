"""Claude Pro/Max subscription quota.

Anthropic exposes no documented API for consumer subscription quota. Two
undocumented routes exist; this adapter prefers the one that works with an
ordinary inference token.

1. anthropic-ratelimit-unified-* response headers  (DEFAULT)
   Returned on any /v1/messages call made with a Claude Code OAuth token.
   Carries the true 5h / 7d subscription windows. Costs ~1 token to read.

2. GET /api/oauth/usage
   Cleaner and free, but requires the `user:profile` scope. Tokens minted for
   inference (e.g. `claude setup-token`) return 403. Tried first only when
   `prefer_oauth_usage` is set.

Both are undocumented and may break without notice.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from ..core import ERROR, LIVE, UNCONFIGURED, Adapter, Result, Window, register
from ._http import fmt_reset, get_json, read_env_file, request

API = "https://api.anthropic.com"
BETA = "oauth-2025-04-20"


def _token(conf: Dict[str, Any]) -> Optional[str]:
    """Find a Claude OAuth token: explicit config, env var, then known files."""
    if conf.get("token"):
        return str(conf["token"])
    if conf.get("token_env") and os.environ.get(conf["token_env"]):
        return os.environ[conf["token_env"]]
    for var in ("AIQUOTA_CLAUDE_TOKEN", "ANTHROPIC_TOKEN", "ANTHROPIC_API_KEY"):
        if os.environ.get(var):
            return os.environ[var]

    # Reading ANOTHER application's credential file is opt-in. Explicit
    # config/env above is fine — you set that deliberately. Silently borrowing
    # Claude Code's or Hermes' OAuth token is not a safe default.
    if os.environ.get("AIQUOTA_NO_AUTODISCOVER"):
        return None
    if not conf.get("autodiscover") and not conf.get("token_files"):
        return None

    for raw in conf.get("token_files") or [
        "~/.hermes/.env::ANTHROPIC_TOKEN",
        "~/.claude/.credentials.json",
        "~/.config/claude/.credentials.json",
        "~/.hermes/.anthropic_oauth.json",
    ]:
        path, _, key = str(raw).partition("::")
        p = os.path.expanduser(path)
        if not os.path.exists(p):
            continue
        if key:
            v = read_env_file(p, key)
            if v:
                return v
            continue
        try:
            with open(p) as f:
                d = json.load(f)
        except Exception:
            continue
        for probe in (d.get("claudeAiOauth"), d):
            if isinstance(probe, dict):
                t = probe.get("accessToken") or probe.get("access_token")
                if t:
                    return t
    return None


def _pct(raw, scale_is_fraction: bool) -> Optional[float]:
    """Convert a utilization reading to a percentage.

    The scale must be decided for the WHOLE response, never per value. The
    original code guessed per value with `u * 100 if u <= 1.0 else u`, which
    is correct right up until a window goes PAST its limit: Anthropic then
    reports 1.02, 1.05, 1.2 — still fractions — and the guess mistook them for
    percentages, so a fully exhausted 5-hour window displayed as "1%".

    That is the most dangerous direction an error can take here: it says you
    have your whole allowance left at the exact moment you have none.

    Percentages are clamped to 100. You cannot use more than all of a window,
    and "102%" invites the reader to wonder whether the tool is broken; the
    raw value is kept in `extra` for anyone who wants it.
    """
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    if scale_is_fraction:
        v *= 100.0
    return round(min(max(v, 0.0), 100.0), 1)


def _fraction_scale(values) -> bool:
    """Decide whether a set of utilization readings is 0-1 or 0-100.

    Judged across every window in one response, so a single over-limit window
    can no longer flip the interpretation for itself. Anything above 1.5 can
    only be a percentage (a fraction that high would mean 150% of a window,
    which the API does not report); otherwise treat the response as fractions.
    """
    nums = []
    for v in values:
        try:
            nums.append(float(v))
        except (TypeError, ValueError):
            continue
    if not nums:
        return True
    return max(nums) <= 1.5


@register
class ClaudeAdapter(Adapter):
    name = "claude"
    service = "Claude"
    summary = "Claude Pro/Max 5h + weekly windows (undocumented headers)"
    setup = ("Needs a Claude Code OAuth token. Set AIQUOTA_CLAUDE_TOKEN, or "
             "install Claude Code so ~/.claude/.credentials.json exists.")
    cost_note = "reads headers from a 1-token Haiku call (negligible quota)"
    defaults = {"probe_model": "claude-haiku-4-5-20251001"}

    def detect(self):
        """Look for Claude OAuth tokens WITHOUT using them."""
        found = []
        candidates = [
            ("~/.claude/.credentials.json", None, "Claude Code login"),
            ("~/.config/claude/.credentials.json", None, "Claude Code login"),
            ("~/.hermes/.env", "ANTHROPIC_TOKEN", "Hermes agent token"),
            ("~/.anthropic_oauth.json", None, "Anthropic OAuth token"),
        ]
        for raw, envkey, label in candidates:
            p = os.path.expanduser(raw)
            if not os.path.exists(p):
                continue
            tok = None
            if envkey:
                tok = read_env_file(p, envkey)
            else:
                try:
                    with open(p) as f:
                        d = json.load(f)
                    for probe in (d.get("claudeAiOauth"), d):
                        if isinstance(probe, dict):
                            tok = probe.get("accessToken") or probe.get("access_token")
                            if tok:
                                break
                except Exception:
                    pass
            if not tok:
                continue
            kind = ("OAuth (subscription)" if str(tok).startswith("sk-ant-oat")
                    else "API key (no subscription quota)"
                    if str(tok).startswith("sk-ant-api") else "token")
            spec = f"{raw}::{envkey}" if envkey else raw
            found.append({
                "source": raw,
                "detail": f"{label} — {kind}",
                "config": {"token_files": [spec]},
            })
        return found

    def probe(self, conf: Dict[str, Any]) -> Result:
        tok = _token(conf)
        if not tok:
            return self.make(conf, tier=UNCONFIGURED, note=self.setup,
                             error="no Claude token found")

        # Read-only usage endpoint FIRST, always.
        #
        # The header route below has to send a real /v1/messages request, and
        # Anthropic's January 2026 server-side enforcement rejects tokens used
        # for "other API requests" outside Claude Code. Reading a usage figure
        # should not require making an inference call at all: it burns quota to
        # measure quota, and it is the exact traffic pattern being policed.
        #
        # Tokens minted by `claude setup-token` / CLAUDE_CODE_OAUTH_TOKEN are
        # inference-only and lack `user:profile`, so this returns 403 for them
        # — hence the fallback, not its removal.
        r = self._via_oauth_usage(conf, tok)
        if r.tier == LIVE:
            return r
        if conf.get("usage_endpoint_only"):
            return r
        fallback = self._via_headers(conf, tok)
        # Be explicit that this reading cost an API call, and why.
        if fallback.tier == LIVE:
            fallback.extra["read_via"] = (
                "inference call — this token lacks the user:profile scope "
                "needed for the read-only usage endpoint")
        return fallback

    # -- route 1: free, but needs user:profile scope -----------------
    def _via_oauth_usage(self, conf, tok) -> Result:
        code, d = get_json(f"{API}/api/oauth/usage", headers={
            "Authorization": f"Bearer {tok}",
            "anthropic-beta": BETA, "anthropic-version": "2023-06-01"})
        r = self.make(conf, tier=LIVE)
        # Providers report a percentage, not counts.
        r.confidence = "percent_only"
        r.extra["source"] = "oauth_usage"
        if code != 200 or not isinstance(d, dict):
            r.tier = ERROR
            r.error = ("token lacks user:profile scope" if code == 403
                       else f"HTTP {code}")
            return r
        # Any bucket may be null (window not started), and resets_at may be
        # null independently of utilization — nil-check both rather than
        # assuming a populated shape.
        labels = {"five_hour": "5-hour session", "seven_day": "Weekly (all)",
                  "seven_day_opus": "Weekly (Opus)",
                  "seven_day_sonnet": "Weekly (Sonnet)",
                  "seven_day_oauth_apps": "Weekly (apps)",
                  "seven_day_cowork": "Weekly (Cowork)"}
        # Decide the scale once, across every window in this response.
        frac = _fraction_scale(
            v.get("utilization") for v in d.values()
            if isinstance(v, dict) and v.get("utilization") is not None)
        for k, lbl in labels.items():
            v = d.get(k)
            if isinstance(v, dict) and v.get("utilization") is not None:
                pct = _pct(v["utilization"], frac)
                if pct is None:
                    continue
                raw_reset = v.get("resets_at")
                # Keep the unclamped reading for anyone who wants to know a
                # window went past its limit rather than merely reached it.
                try:
                    rawv = float(v["utilization"]) * (100.0 if frac else 1.0)
                    if rawv > 100.0:
                        r.extra.setdefault("over_limit", {})[k] = round(rawv, 1)
                except (TypeError, ValueError):
                    pass
                r.windows.append(Window(
                    key=k, label=lbl, used_pct=pct,
                    resets_at=(fmt_reset(raw_reset) or raw_reset or "")
                    if raw_reset else ""))
        ex = d.get("extra_usage")
        if isinstance(ex, dict) and ex.get("used_credits") is not None:
            # Reported in cents.
            try:
                r.extra["extra_usage_spend"] = float(ex["used_credits"]) / 100.0
            except (TypeError, ValueError):
                pass
            if ex.get("currency"):
                r.extra["extra_usage_currency"] = ex["currency"]
        if not r.windows:
            r.tier, r.error = ERROR, "no windows in response"
        return r

    # -- route 2: works with a plain inference token -----------------
    def _via_headers(self, conf, tok) -> Result:
        model = conf.get("probe_model") or self.defaults["probe_model"]
        payload = json.dumps({"model": model, "max_tokens": 1,
                              "messages": [{"role": "user", "content": "."}]}).encode()
        code, hdrs, _ = request(f"{API}/v1/messages", headers={
            "content-type": "application/json",
            "authorization": f"Bearer {tok}",
            "anthropic-version": "2023-06-01",
            "anthropic-beta": BETA}, data=payload, timeout=40)

        r = self.make(conf, tier=LIVE)
        r.extra["source"] = "unified_headers"
        if not any("unified" in k for k in hdrs):
            r.tier = ERROR
            r.error = (f"HTTP {code}: no unified headers "
                       "(token may be an API key, not a subscription OAuth token)")
            return r

        tags = (("5h", "5-hour session"), ("7d", "Weekly (all)"),
                ("7d_oi", "Weekly (Opus)"))
        # Same rule as the usage endpoint: one scale for the whole response.
        frac = _fraction_scale(
            hdrs.get(f"anthropic-ratelimit-unified-{t}-utilization")
            for t, _ in tags)
        for tag, lbl in tags:
            u = hdrs.get(f"anthropic-ratelimit-unified-{tag}-utilization")
            if u is None:
                continue
            pct = _pct(u, frac)
            if pct is None:
                continue
            try:
                rawv = float(u) * (100.0 if frac else 1.0)
                if rawv > 100.0:
                    r.extra.setdefault("over_limit", {})[tag] = round(rawv, 1)
            except (TypeError, ValueError):
                pass
            r.windows.append(Window(
                key=tag, label=lbl, used_pct=pct,
                resets_at=fmt_reset(hdrs.get(f"anthropic-ratelimit-unified-{tag}-reset")),
                status=hdrs.get(f"anthropic-ratelimit-unified-{tag}-status")))

        for hk, ek in (("representative-claim", "binding"),
                       ("status", "overall_status"),
                       ("overage-status", "overage"),
                       ("fallback-percentage", "fallback_pct")):
            v = hdrs.get(f"anthropic-ratelimit-unified-{hk}")
            if v:
                r.extra[ek] = v
        if not r.windows:
            r.tier, r.error = ERROR, "unified headers present but unparseable"
        return r
