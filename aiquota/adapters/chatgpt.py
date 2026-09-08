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


def _auth(conf: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    if conf.get("token"):
        return str(conf["token"]), conf.get("account_id")
    if os.environ.get("AIQUOTA_CODEX_TOKEN"):
        return os.environ["AIQUOTA_CODEX_TOKEN"], os.environ.get("AIQUOTA_CODEX_ACCOUNT")

    if os.environ.get("AIQUOTA_NO_AUTODISCOVER") or conf.get("no_autodiscover"):
        return None, None

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
            return tok, acct
    return None, None


@register
class ChatGPTAdapter(Adapter):
    name = "chatgpt"
    service = "ChatGPT"
    summary = "Codex/Work usage windows (NOT general chat quota)"
    setup = ("Needs a Codex CLI login (~/.codex/auth.json) or "
             "AIQUOTA_CODEX_TOKEN. Only covers the Codex/Work meter.")

    def probe(self, conf: Dict[str, Any]) -> Result:
        tok, acct = _auth(conf)
        if not tok:
            return self.make(conf, tier=UNCONFIGURED, note=self.setup,
                             error="no Codex credentials found")

        hdr = {"Authorization": f"Bearer {tok}"}
        if acct:
            hdr["ChatGPT-Account-Id"] = acct
        code, d = get_json(URL, headers=hdr, timeout=25)

        r = self.make(conf, tier=LIVE, note="Codex/Work meter")
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
