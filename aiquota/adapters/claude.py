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

    # Scanning other apps' credential files is convenient but surprising.
    # Allow opting out (also keeps test runs hermetic).
    if os.environ.get("AIQUOTA_NO_AUTODISCOVER") or conf.get("no_autodiscover"):
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


@register
class ClaudeAdapter(Adapter):
    name = "claude"
    service = "Claude"
    summary = "Claude Pro/Max 5h + weekly windows (undocumented headers)"
    setup = ("Needs a Claude Code OAuth token. Set AIQUOTA_CLAUDE_TOKEN, or "
             "install Claude Code so ~/.claude/.credentials.json exists.")
    cost_note = "reads headers from a 1-token Haiku call (negligible quota)"
    defaults = {"probe_model": "claude-haiku-4-5-20251001"}

    def probe(self, conf: Dict[str, Any]) -> Result:
        tok = _token(conf)
        if not tok:
            return self.make(conf, tier=UNCONFIGURED, note=self.setup,
                             error="no Claude token found")

        if conf.get("prefer_oauth_usage"):
            r = self._via_oauth_usage(conf, tok)
            if r.tier == LIVE:
                return r
        return self._via_headers(conf, tok)

    # -- route 1: free, but needs user:profile scope -----------------
    def _via_oauth_usage(self, conf, tok) -> Result:
        code, d = get_json(f"{API}/api/oauth/usage", headers={
            "Authorization": f"Bearer {tok}",
            "anthropic-beta": BETA, "anthropic-version": "2023-06-01"})
        r = self.make(conf, tier=LIVE)
        r.extra["source"] = "oauth_usage"
        if code != 200 or not isinstance(d, dict):
            r.tier = ERROR
            r.error = ("token lacks user:profile scope" if code == 403
                       else f"HTTP {code}")
            return r
        labels = {"five_hour": "5-hour session", "seven_day": "Weekly (all)",
                  "seven_day_opus": "Weekly (Opus)",
                  "seven_day_sonnet": "Weekly (Sonnet)"}
        for k, lbl in labels.items():
            v = d.get(k)
            if isinstance(v, dict) and v.get("utilization") is not None:
                try:
                    u = float(v["utilization"])
                except (TypeError, ValueError):
                    continue
                r.windows.append(Window(
                    key=k, label=lbl,
                    used_pct=round(u * 100 if u <= 1.0 else u, 1),
                    resets_at=fmt_reset(v.get("resets_at")) or v.get("resets_at")))
        ex = d.get("extra_usage")
        if isinstance(ex, dict) and ex.get("used_credits") is not None:
            r.extra["extra_usage_credits"] = ex["used_credits"]
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

        for tag, lbl in (("5h", "5-hour session"), ("7d", "Weekly (all)"),
                         ("7d_oi", "Weekly (Opus)")):
            u = hdrs.get(f"anthropic-ratelimit-unified-{tag}-utilization")
            if u is None:
                continue
            try:
                val = float(u)
            except ValueError:
                continue
            r.windows.append(Window(
                key=tag, label=lbl,
                used_pct=round(val * 100 if val <= 1.0 else val, 1),
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
