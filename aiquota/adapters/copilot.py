"""GitHub Copilot quota, via your existing `gh` CLI login.

Reuses the GitHub CLI credential already on the machine (with consent) —
no key pasting, no separate login. Reads:

  GET https://api.github.com/copilot_internal/user

which returns the caller's Copilot plan and, for subscribers, quota
snapshots. This endpoint is undocumented (it backs the editor plugins), so
the quota field names are handled defensively: if they are absent we report
the plan rather than inventing numbers.
"""
from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Dict, Optional

from ..core import ERROR, LIVE, MANUAL, UNCONFIGURED, Adapter, Result, Window, register
from ._http import fmt_reset, get_json

URL = "https://api.github.com/copilot_internal/user"


def _gh_token() -> Optional[str]:
    """Ask the gh CLI for its token. Never reads the keyring directly."""
    for env in ("AIQUOTA_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
        if os.environ.get(env):
            return os.environ[env]
    try:
        p = subprocess.run(["gh", "auth", "token"],
                           capture_output=True, text=True, timeout=15)
        if p.returncode == 0 and p.stdout.strip():
            return p.stdout.strip()
    except (FileNotFoundError, subprocess.SubprocessError):
        pass
    return None


@register
class CopilotAdapter(Adapter):
    name = "copilot"
    service = "GitHub Copilot"
    summary = "Copilot plan + premium request quota (via gh CLI login)"
    setup = ("Sign in with the GitHub CLI: `gh auth login`. "
             "aiquota reuses that login — nothing to paste.")

    def detect(self):
        """Report a usable gh login WITHOUT using it."""
        if os.environ.get("AIQUOTA_NO_AUTODISCOVER"):
            return []
        try:
            p = subprocess.run(["gh", "auth", "status"],
                               capture_output=True, text=True, timeout=15)
        except (FileNotFoundError, subprocess.SubprocessError):
            return []
        if p.returncode != 0:
            return []
        who = ""
        for line in (p.stdout + p.stderr).splitlines():
            if "account" in line:
                parts = line.split("account")
                if len(parts) > 1:
                    who = parts[1].strip().split()[0]
                    break
        return [{
            "source": "gh CLI",
            "detail": f"GitHub CLI login{' — ' + who if who else ''}",
            "config": {"autodiscover": True},
        }]

    def probe(self, conf: Dict[str, Any]) -> Result:
        if not conf.get("autodiscover") and not conf.get("token"):
            if self.detect():
                return self.make(
                    conf, tier=UNCONFIGURED,
                    note="Found a GitHub CLI login but did not use it. "
                         "Reading it is opt-in: aiquota link copilot",
                    error="credentials available but not authorised")
            return self.make(conf, tier=UNCONFIGURED, note=self.setup,
                             error="no GitHub login found")

        tok = conf.get("token") or _gh_token()
        if not tok:
            return self.make(conf, tier=UNCONFIGURED, note=self.setup,
                             error="could not read a GitHub token")

        code, d = get_json(URL, headers={
            "Authorization": f"token {tok}",
            "Accept": "application/json",
            "Editor-Version": "aiquota/0.1",
        }, timeout=25)

        r = self.make(conf, tier=LIVE)
        if code != 200 or not isinstance(d, dict):
            r.tier = ERROR
            r.error = ("GitHub token rejected — run `gh auth login`"
                       if code in (401, 403) else f"HTTP {code}")
            return r

        plan = d.get("copilot_plan")
        sku = d.get("access_type_sku")
        if plan:
            r.plan = str(plan).replace("_", " ").title()

        # No active subscription: say so plainly instead of showing 0%.
        if sku == "no_access" or d.get("chat_enabled") is False and not plan:
            r.tier = MANUAL
            r.note = "No active Copilot subscription on this account"
            return r

        # Quota snapshots appear for subscribers. Field names are not
        # documented, so probe defensively and never fabricate a denominator.
        snaps = d.get("quota_snapshots")
        if isinstance(snaps, dict):
            for qkey, label in (("premium_interactions", "Premium requests"),
                                ("chat", "Chat"),
                                ("completions", "Completions")):
                q = snaps.get(qkey)
                if not isinstance(q, dict):
                    continue
                if q.get("unlimited"):
                    r.extra[label.lower()] = "unlimited"
                    continue
                pct = q.get("percent_remaining")
                if pct is None:
                    continue
                try:
                    r.windows.append(Window(
                        key=qkey, label=label,
                        used_pct=round(max(0.0, min(100.0, 100 - float(pct))), 1),
                        resets_at=fmt_reset(d.get("quota_reset_date"))
                        or d.get("quota_reset_date")))
                except (TypeError, ValueError):
                    pass

        if not r.windows:
            r.note = f"Plan: {r.plan or 'unknown'} (no quota data returned)"
        return r
