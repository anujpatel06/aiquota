"""ElevenLabs character quota — a documented, supported API.

GET https://api.elevenlabs.io/v1/user/subscription
    xi-api-key: <key>
returns {tier, character_count, character_limit,
         next_character_count_reset_unix, status}

Unlike the Claude/ChatGPT adapters this is an official endpoint, so it is
stable and safe to rely on. The API key IS the login: paste it once and
usage is fetched live from then on.
"""
from __future__ import annotations

import os
from typing import Any, Dict

from ..core import ERROR, LIVE, UNCONFIGURED, Adapter, Result, Window, register
from ._http import fmt_reset, get_json

URL = "https://api.elevenlabs.io/v1/user/subscription"


@register
class ElevenLabsAdapter(Adapter):
    name = "elevenlabs"
    service = "ElevenLabs"
    summary = "Character quota + reset date (official API)"
    setup = ("Needs an API key from elevenlabs.io → Profile → API Key. "
             "Set AIQUOTA_ELEVENLABS_KEY or run `aiquota link elevenlabs`.")
    api_key_label = "ElevenLabs API key"
    api_key_help = "elevenlabs.io → click your avatar → API Key"

    def _key(self, conf: Dict[str, Any]):
        return (conf.get("api_key")
                or os.environ.get("AIQUOTA_ELEVENLABS_KEY")
                or os.environ.get("ELEVENLABS_API_KEY"))

    def probe(self, conf: Dict[str, Any]) -> Result:
        key = self._key(conf)
        if not key:
            return self.make(conf, tier=UNCONFIGURED, note=self.setup,
                             error="no API key")

        code, d = get_json(URL, headers={"xi-api-key": str(key)}, timeout=25)
        r = self.make(conf, tier=LIVE)
        if code != 200 or not isinstance(d, dict):
            r.tier = ERROR
            r.error = ("invalid API key" if code in (401, 403)
                       else f"HTTP {code}")
            return r

        if d.get("tier"):
            r.plan = str(d["tier"]).title()

        used = d.get("character_count")
        limit = d.get("character_limit")
        if used is not None and limit:
            try:
                pct = float(used) / float(limit) * 100
                r.windows.append(Window(
                    key="characters", label="Characters",
                    used_pct=round(max(0.0, min(100.0, pct)), 1),
                    resets_at=fmt_reset(d.get("next_character_count_reset_unix"))))
                r.extra["used"] = int(used)
                r.extra["limit"] = int(limit)
                r.extra["remaining"] = int(limit) - int(used)
            except (TypeError, ValueError, ZeroDivisionError):
                pass

        if d.get("status") and d["status"] != "active":
            r.extra["status"] = d["status"]
        if not r.windows:
            r.note = "No character quota reported"
        return r
