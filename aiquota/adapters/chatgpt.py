"""ChatGPT / Codex quota.

IMPORTANT SCOPE LIMIT: this reads the **Codex / Work** meter, not general
ChatGPT chat quota. `chatgpt.com/backend-api/wham/usage` is the endpoint
OpenAI's own open-source Codex client calls; general chat windows have no
reachable endpoint. A ChatGPT Plus subscription and OpenAI API billing are
entirely separate products — the documented /v1/usage endpoints report API
spend and know nothing about your Plus limits.

Undocumented and private; may break without notice.
"""
from __future__ import annotations

import base64
import json
import os
from typing import Any, Dict, Optional, Tuple

from ..core import ERROR, LIVE, UNCONFIGURED, Adapter, Result, Window, register
from ._http import fmt_reset, get_json

URL = "https://chatgpt.com/backend-api/wham/usage"


def _auth(conf: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], str]:
    """Return (token, account_id, source_description).

    Explicit config and env vars are used freely — you set those on purpose.
    Reading ANOTHER application's credential file is different: it's someone
    else's login, so it requires opt-in via `autodiscover: true`.
    """
    if conf.get("token"):
        return str(conf["token"]), conf.get("account_id"), "config"
    if os.environ.get("AIQUOTA_CODEX_TOKEN"):
        return (os.environ["AIQUOTA_CODEX_TOKEN"],
                os.environ.get("AIQUOTA_CODEX_ACCOUNT"), "env")

    # Opt-in only. Off by default: silently borrowing another app's OAuth
    # token and sending it to a remote endpoint is not a safe default.
    if os.environ.get("AIQUOTA_NO_AUTODISCOVER"):
        return None, None, ""
    if not conf.get("autodiscover"):
        return None, None, "needs_optin"

    for raw in conf.get("auth_files") or ["~/.codex/auth.json"]:
        p = os.path.expanduser(str(raw))
        if not os.path.exists(p):
            continue
        try:
            with open(p) as f:
                d = json.load(f)
        except Exception:
            continue
        t = d.get("tokens") if isinstance(d.get("tokens"), dict) else d
        tok = t.get("access_token") or t.get("accessToken")
        acct = (t.get("account_id") or t.get("accountId")
                or d.get("account_id") or d.get("accountId"))
        if tok and not acct:
            # account_id is frequently null in auth.json; the id_token carries
            # it as a claim. Without it the usage endpoint answers for the
            # wrong workspace (or refuses).
            acct = _account_from_jwt(t.get("id_token") or tok)
        if tok:
            return tok, acct, f"borrowed from {raw}"
    return None, None, ""


def _account_from_jwt(jwt: Optional[str]) -> Optional[str]:
    """Pull chatgpt_account_id out of a JWT payload. No signature check —
    this is reading our own local token for a routing hint, not trusting it."""
    if not jwt or jwt.count(".") < 2:
        return None
    try:
        payload = jwt.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        d = json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return None
    for ns in ("https://api.openai.com/auth",):
        v = d.get(ns)
        if isinstance(v, dict) and v.get("chatgpt_account_id"):
            return str(v["chatgpt_account_id"])
    return d.get("chatgpt_account_id") or None


def _consumer_limits(token: str, account_id: Optional[str]):
    """Feature credits for a consumer ChatGPT plan.

    POST /backend-api/conversation/init returns a `limits_progress` array —
    absolute remaining counts for Deep Research, image generation, file
    uploads and whatever else the account has. It creates no conversation and
    spends no quota.

    Plain chat/GPT-5 messages are NOT in there. Nothing readable reports them:
    every extension claiming "X of Y messages left" counts locally in the tab
    against a hard-coded plan table. aiquota shows what the server actually
    says and stays quiet about the rest.

    Returns (status, list) — the list is empty when the account has no
    metered features.
    """
    body = json.dumps({
        "gizmo_id": None, "requested_default_model": None,
        "conversation_id": None, "timezone_offset_min": 0,
        "system_hints": [],
    }).encode()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Origin": "https://chatgpt.com",
        "Referer": "https://chatgpt.com/",
        "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/152.0.0.0 Safari/537.36"),
    }
    if account_id:
        headers["ChatGPT-Account-Id"] = account_id
    code, data = get_json("https://chatgpt.com/backend-api/conversation/init",
                          headers=headers, data=body)
    if code != 200 or not isinstance(data, dict):
        return code, []
    out = []
    for item in data.get("limits_progress") or []:
        if not isinstance(item, dict):
            continue
        name = item.get("feature_name")
        rem = item.get("remaining")
        if not name or rem is None:
            continue
        out.append({"feature": str(name), "remaining": rem,
                    "resets_at": item.get("reset_after")})
    return code, out


@register
class ChatGPTAdapter(Adapter):
    name = "chatgpt"
    service = "ChatGPT"
    summary = "Codex/Work usage windows (NOT general chat quota)"
    setup = ("Needs a Codex CLI login. Enable with: "
             "aiquota set chatgpt autodiscover=true  (reads ~/.codex/auth.json), "
             "or set AIQUOTA_CODEX_TOKEN. Covers the Codex/Work meter only.")

    def detect(self):
        """Look for a Codex login WITHOUT using it."""
        found = []
        for raw in ["~/.codex/auth.json"]:
            p = os.path.expanduser(raw)
            if not os.path.exists(p):
                continue
            try:
                with open(p) as f:
                    d = json.load(f)
            except Exception:
                continue
            t = d.get("tokens") if isinstance(d.get("tokens"), dict) else d
            if not (t.get("access_token") or t.get("accessToken")):
                continue
            acct = (t.get("account_id") or t.get("accountId") or "")
            detail = "Codex CLI login"
            if d.get("auth_mode"):
                detail += f" (auth_mode: {d['auth_mode']})"
            if acct:
                detail += f", account {acct[:8]}…"
            if d.get("last_refresh"):
                detail += f", last refreshed {str(d['last_refresh'])[:10]}"
            found.append({"source": raw, "detail": detail,
                          "config": {"autodiscover": True}})
        return found

    def probe(self, conf: Dict[str, Any]) -> Result:
        tok, acct, source = _auth(conf)
        if not tok:
            if source == "needs_optin":
                return self.make(
                    conf, tier=UNCONFIGURED,
                    note="Found a Codex login on this machine but did not use "
                         "it. Reading another app's credentials is opt-in: "
                         "aiquota set chatgpt autodiscover=true",
                    error="credentials available but not authorised")
            return self.make(conf, tier=UNCONFIGURED, note=self.setup,
                             error="no Codex credentials found")

        hdr = {"Authorization": f"Bearer {tok}"}
        if acct:
            hdr["ChatGPT-Account-Id"] = acct
        code, d = get_json(URL, headers=hdr, timeout=25)

        r = self.make(conf, tier=LIVE, note="Codex/Work meter")
        # Providers report a percentage, not counts.
        r.confidence = "percent_only"
        r.extra["credential_source"] = source
        if code != 200 or not isinstance(d, dict):
            r.tier = ERROR
            r.error = ("Codex token expired — run `codex login`" if code == 401
                       else f"HTTP {code}")
            return r

        if d.get("plan_type"):
            r.plan = f"ChatGPT ({d['plan_type']})"
        rl = d.get("rate_limit") or {}
        for wk, fallback in (("primary_window", "Primary"),
                             ("secondary_window", "Secondary")):
            w = rl.get(wk)
            if not isinstance(w, dict) or w.get("used_percent") is None:
                continue
            secs = w.get("limit_window_seconds")
            lbl = fallback
            if secs:
                lbl = (f"{round(secs/86400)}-day" if secs >= 86400
                       else f"{round(secs/3600)}-hour")
            try:
                pct = round(float(w["used_percent"]), 1)
            except (TypeError, ValueError):
                continue
            r.windows.append(Window(key=wk, label=lbl, used_pct=pct,
                                    resets_at=fmt_reset(w.get("reset_at"))))

        cr = d.get("credits") or {}
        if isinstance(cr, dict):
            if cr.get("unlimited"):
                r.extra["credits"] = "unlimited"
            elif cr.get("balance") not in (None, ""):
                r.extra["credits"] = cr["balance"]
        if rl.get("limit_reached"):
            r.extra["limit_reached"] = True

        # Consumer feature credits — Deep Research, image generation and
        # friends. Separate meter from the Codex windows above, and often the
        # only thing a Plus subscriber actually cares about.
        if conf.get("consumer_limits", True):
            try:
                _c, feats = _consumer_limits(tok, acct)
            except Exception:
                feats = []
            for f in feats:
                label = f["feature"].replace("_", " ").title()
                r.extra[f"{f['feature']}_remaining"] = f["remaining"]
                # These are absolute counts with no published cap, so they are
                # reported as a number, never as a percentage of a guess.
                r.extra.setdefault("features", []).append(
                    f"{label}: {f['remaining']}")
            if feats:
                r.extra["features_note"] = (
                    "remaining counts; plain chat messages are not reported "
                    "by any endpoint")

        if not r.windows:
            r.note = "No usage windows returned (plan may be unlimited)"
        return r
