"""Adapters for providers no HTTP client can reach — only a real browser.

Both of these refuse a stdlib request outright, for different reasons:

    Perplexity   Cloudflare fingerprints the TLS handshake, so urllib gets a
                 "Just a moment..." challenge page no matter what headers or
                 cookies it sends.

Verified by running the same request from inside a Chrome page instead —
Perplexity answered 200 with real JSON, so the reading is taken in the
browser window rather than by the adapter.

Because of that, these two store their usage at sign-in time and re-read it
by briefly reopening the window on refresh. That is heavier than a plain HTTP
call, which is why only the providers that genuinely need it work this way.
"""
from __future__ import annotations

from typing import Any, Dict, List

from ..core import ERROR, LIVE, UNCONFIGURED, Adapter, Result, Window, register


class BrowserReadAdapter(Adapter):
    """Signs in, reads its endpoints in-page, and caches what it saw."""

    login_url = ""
    endpoints: List[str] = []
    cookie_domains: List[str] = []
    want_cookies: List[str] = []

    @property
    def browser_login(self):
        return {"url": self.login_url, "domains": self.cookie_domains,
                "want": self.want_cookies,
                "read": self.endpoints,           # picker reads these in-page
                "label": f"Sign in to {self.service}"}

    def probe(self, conf: Dict[str, Any]) -> Result:
        data = conf.get("readings")
        if not data:
            if not conf.get("session"):
                return self.make(conf, tier=UNCONFIGURED, note=self.setup,
                                 error="not signed in")
            r = self.make(conf, tier=ERROR)
            r.error = "no readings captured — sign in again"
            return r
        return self.parse(conf, data)

    def parse(self, conf, data) -> Result:  # pragma: no cover - overridden
        raise NotImplementedError


@register
class PerplexityAdapter(BrowserReadAdapter):
    name = "perplexity"
    service = "Perplexity"
    summary = "Pro search quota and limits"
    setup = "Sign in through your browser — click Add in the widget."
    login_url = "https://www.perplexity.ai/"
    endpoints = ["https://www.perplexity.ai/rest/user/settings"]
    cookie_domains = ["perplexity.ai"]
    want_cookies = ["__Secure-next-auth.session-token"]

    def parse(self, conf, data) -> Result:
        d = data.get(self.endpoints[0]) or {}
        r = self.make(conf, tier=LIVE)
        if d.get("subscription_status"):
            r.plan = str(d["subscription_status"]).title()

        # Documented counters in /rest/user/settings. Only emit a window when
        # both a use and a limit are present — never infer one.
        pairs = [
            ("gpt4_limit", "gpt4_used", "Pro searches"),
            ("opus_limit", "opus_used", "Opus"),
            ("o1_limit", "o1_used", "Reasoning"),
            ("create_limit", "create_used", "Create"),
        ]
        for cap_key, used_key, label in pairs:
            cap, used = d.get(cap_key), d.get(used_key)
            if cap in (None, 0) or used is None:
                continue
            try:
                r.windows.append(Window(
                    key=cap_key, label=label,
                    used_pct=round(float(used) / float(cap) * 100, 1),
                    resets_at=""))
                r.extra[f"{label}_used"] = used
                r.extra[f"{label}_limit"] = cap
            except (TypeError, ValueError, ZeroDivisionError):
                continue

        if not r.windows:
            # Signed in, but this account exposes no counters. Say so rather
            # than inventing a percentage.
            r.note = "signed in — no usage counters exposed"
        return r


