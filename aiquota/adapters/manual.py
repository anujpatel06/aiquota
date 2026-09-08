"""Manual adapter — track ANY service with no API, without writing code.

    aiquota add midjourney --adapter manual --plan "Standard" \\
        --set credits=120 --set credits_total=900 --set renews_on=2026-10-01

This is the escape hatch that makes the tool cover every subscription a person
actually has, not just the ones with reachable endpoints.
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional

from ..core import MANUAL, Adapter, Result, Window, register


def days_until(datestr: Optional[str]) -> Optional[int]:
    if not datestr:
        return None
    try:
        t = time.mktime(time.strptime(str(datestr), "%Y-%m-%d"))
        return max(0, int((t - time.time()) // 86400))
    except (ValueError, TypeError):
        return None


@register
class ManualAdapter(Adapter):
    name = "manual"
    service = "Manual"
    summary = "User-entered credits / renewal date for services with no API"
    setup = ("aiquota set <name> credits=120 credits_total=900 "
             "renews_on=2026-10-01")

    def probe(self, conf: Dict[str, Any]) -> Result:
        # service = the brand ("Higgsfield"); plan = the tier ("Creator").
        # Falls back to the config key so a bare `add foo --adapter manual` works.
        service = conf.get("service") or conf.get("_key") or "Service"
        r = Result(name=self.name, service=str(service).title()
                   if str(service).islower() else str(service),
                   plan=conf.get("plan") or "", tier=MANUAL,
                   note=conf.get("note") or "")

        credits = conf.get("credits")
        total = conf.get("credits_total")
        if credits is not None:
            r.extra["credits"] = credits
            if total:
                try:
                    pct = (1 - float(credits) / float(total)) * 100
                    r.windows.append(Window(key="credits", label="Credits used",
                                            used_pct=round(max(0.0, min(100.0, pct)), 1)))
                except (TypeError, ValueError, ZeroDivisionError):
                    pass

        used, limit = conf.get("used"), conf.get("limit")
        if used is not None and limit:
            try:
                pct = float(used) / float(limit) * 100
                r.windows.append(Window(
                    key="used", label=conf.get("unit_label") or "Used",
                    used_pct=round(max(0.0, min(100.0, pct)), 1)))
            except (TypeError, ValueError, ZeroDivisionError):
                pass

        d = days_until(conf.get("renews_on"))
        if d is not None:
            r.extra["renews_in_days"] = d
            r.extra["renews_on"] = conf.get("renews_on")
        if conf.get("updated"):
            r.extra["updated"] = conf["updated"]
        if not r.windows and not r.note:
            r.note = "No API — values entered manually"
        return r
