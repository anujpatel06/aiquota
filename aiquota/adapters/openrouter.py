"""OpenRouter credit balance — a documented, supported API.

GET https://openrouter.ai/api/v1/key
    Authorization: Bearer <key>
returns {data: {label, usage, limit, limit_remaining, is_free_tier, ...}}

`limit` is null on pay-as-you-go accounts with no cap, in which case there is
no percentage to show — we report spend instead of inventing a denominator.
"""
from __future__ import annotations

import os
from typing import Any, Dict

from ..core import ERROR, LIVE, UNCONFIGURED, Adapter, Result, Window, register
from ._http import get_json

URL = "https://openrouter.ai/api/v1/key"


@register
class OpenRouterAdapter(Adapter):
    name = "openrouter"
    service = "OpenRouter"
    summary = "Credit balance and spend (official API)"
    setup = ("Sign in through your browser — run `aiquota link openrouter` "
             "or click Add in the widget.")
    api_key_label = "OpenRouter API key"
    api_key_help = "openrouter.ai → Keys → create or copy a key"
    # Browser sign-in (OAuth PKCE) — no key pasting needed.
    oauth_login = "openrouter"
    oauth_label = "Sign in with OpenRouter"

    def _key(self, conf: Dict[str, Any]):
        return (conf.get("api_key")
                or os.environ.get("AIQUOTA_OPENROUTER_KEY")
                or os.environ.get("OPENROUTER_API_KEY"))

    def probe(self, conf: Dict[str, Any]) -> Result:
        key = self._key(conf)
        if not key:
            return self.make(conf, tier=UNCONFIGURED, note=self.setup,
                             error="no API key")

        code, d = get_json(URL, headers={"Authorization": f"Bearer {key}"},
                           timeout=25)
        r = self.make(conf, tier=LIVE)
        if code != 200 or not isinstance(d, dict):
            r.tier = ERROR
            r.error = ("invalid API key" if code in (401, 403)
                       else f"HTTP {code}")
            return r

        data = d.get("data") if isinstance(d.get("data"), dict) else d
        usage = data.get("usage")
        limit = data.get("limit")
        remaining = data.get("limit_remaining")

        if limit not in (None, "") and usage is not None:
            try:
                pct = float(usage) / float(limit) * 100
                r.windows.append(Window(
                    key="credits", label="Credits used",
                    used_pct=round(max(0.0, min(100.0, pct)), 1)))
            except (TypeError, ValueError, ZeroDivisionError):
                pass
        elif usage is not None:
            # No cap set — a percentage would be meaningless, so show spend.
            r.note = "no credit limit set"

        if usage is not None:
            try:
                r.extra["spent"] = f"${float(usage):,.2f}"
            except (TypeError, ValueError):
                pass
        if remaining not in (None, ""):
            try:
                r.extra["credits"] = f"${float(remaining):,.2f} left"
            except (TypeError, ValueError):
                pass
        if data.get("is_free_tier"):
            r.plan = "Free tier"
        if data.get("label"):
            r.extra["key_label"] = data["label"]
        return r
