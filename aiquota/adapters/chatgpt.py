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
        if tok:
            return tok, acct, f"borrowed from {raw}"
    return None, None, ""


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
        if not r.windows:
            r.note = "No usage windows returned (plan may be unlimited)"
        return r
