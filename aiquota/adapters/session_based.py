"""Adapters for services whose quota is only exposed to a signed-in session.

These platforms publish no developer API for subscription usage, but their own
web dashboards read it from an internal endpoint. Probing unauthenticated shows
the routes exist and simply want a session:

    cursor.com/api/usage                          401 not_authenticated
    grok.com/rest/subscriptions                   401 No credentials presented
    api.runwayml.com/v1/profile                   401 No authorization token

So the honest options are "type the numbers yourself" or "sign in and let the
dashboard's own endpoint answer". This module is the second one.

None of these providers restrict third-party access to a user's own account the
way Anthropic does — that distinction is recorded in login_policy.py, which
gates whether the picker will even offer sign-in.

The session comes from a browser window aiquota opened, never from the user's
own browser profile.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..core import ERROR, LIVE, UNCONFIGURED, Adapter, Result, Window, register
from ._http import fmt_reset, get_json


class SessionAdapter(Adapter):
    """Base: sign in via browser, then read one JSON endpoint with cookies."""

    # subclasses set these
    usage_url = ""
    login_url = ""
    cookie_domains: List[str] = []
    want_cookies: List[str] = []
    extra_headers: Dict[str, str] = {}

    @property
    def browser_login(self):
        return {"url": self.login_url, "domains": self.cookie_domains,
                "want": self.want_cookies,
                "label": f"Sign in to {self.service}"}

    def _cookie_header(self, conf) -> Optional[str]:
        sess = conf.get("session")
        if isinstance(sess, dict) and sess:
            return "; ".join(f"{k}={v}" for k, v in sess.items())
        return None

    def probe(self, conf: Dict[str, Any]) -> Result:
        cookie = self._cookie_header(conf)
        if not cookie:
            return self.make(conf, tier=UNCONFIGURED, note=self.setup,
                             error="not signed in")
        headers = {"Cookie": cookie, "Accept": "application/json",
                   "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X "
                                  "10_15_7) AppleWebKit/537.36 (KHTML, like "
                                  "Gecko) Chrome/152.0.0.0 Safari/537.36")}
        headers.update(self.extra_headers)
        code, data = get_json(self.usage_url, headers=headers)
        if code in (401, 403):
            r = self.make(conf, tier=ERROR)
            r.error = "session expired — sign in again"
            return r
        if code != 200 or not isinstance(data, dict):
            r = self.make(conf, tier=ERROR)
            r.error = f"HTTP {code}"
            return r
        return self.parse(conf, data)

    def parse(self, conf, data) -> Result:  # pragma: no cover - overridden
        raise NotImplementedError


@register
class CursorAdapter(SessionAdapter):
    name = "cursor"
    service = "Cursor"
    summary = "Request quota for the current billing period"
    setup = "Sign in through your browser — click Add in the widget."
    usage_url = "https://cursor.com/api/usage"
    login_url = "https://cursor.com/dashboard"
    cookie_domains = ["cursor.com"]
    want_cookies = ["WorkosCursorSessionToken"]

    def parse(self, conf, d) -> Result:
        r = self.make(conf, tier=LIVE)
        # Shape: {"gpt-4": {"numRequests": N, "maxRequestUsage": M}, ...}
        for key, v in d.items():
            if not isinstance(v, dict):
                continue
            used = v.get("numRequests")
            cap = v.get("maxRequestUsage")
            if used is None or not cap:
                continue
            try:
                pct = round(float(used) / float(cap) * 100, 1)
            except (TypeError, ValueError, ZeroDivisionError):
                continue
            r.windows.append(Window(key=key, label=key, used_pct=pct,
                                    resets_at=""))
            r.extra[f"{key}_used"] = used
            r.extra[f"{key}_limit"] = cap
        if d.get("startOfMonth"):
            r.extra["period_start"] = d["startOfMonth"]
        if not r.windows:
            r.tier, r.error = ERROR, "no quota fields in response"
        return r



@register
class GrokAdapter(SessionAdapter):
    name = "grok"
    service = "Grok"
    summary = "Subscription tier and request quota"
    setup = "Sign in through your browser — click Add in the widget."
    usage_url = "https://grok.com/rest/subscriptions"
    login_url = "https://grok.com"
    cookie_domains = ["grok.com", "x.ai"]
    want_cookies = ["sso"]

    def parse(self, conf, d) -> Result:
        r = self.make(conf, tier=LIVE)
        tier = d.get("tier") or d.get("subscription_tier")
        if tier:
            r.plan = str(tier)
        for k in ("remaining_queries", "queries_remaining"):
            if d.get(k) is not None and d.get("query_limit"):
                try:
                    cap = float(d["query_limit"])
                    used = cap - float(d[k])
                    r.windows.append(Window(
                        key="queries", label="Queries",
                        used_pct=round(used / cap * 100, 1),
                        resets_at=fmt_reset(d.get("resets_at")) or ""))
                except (TypeError, ValueError, ZeroDivisionError):
                    pass
                break
        if not r.windows:
            # Tier alone is still worth showing; don't invent a percentage.
            r.note = "signed in — no numeric quota exposed"
        return r


@register
class RunwayAdapter(SessionAdapter):
    name = "runway"
    service = "Runway"
    summary = "Credit balance"
    setup = "Sign in through your browser — click Add in the widget."
    usage_url = "https://api.runwayml.com/v1/profile"
    login_url = "https://app.runwayml.com/login"
    cookie_domains = ["runwayml.com"]
    want_cookies = ["session"]

    def parse(self, conf, d) -> Result:
        r = self.make(conf, tier=LIVE)
        user = d.get("user") if isinstance(d.get("user"), dict) else d
        credits = user.get("credits") or user.get("creditBalance")
        if credits is not None:
            r.extra["credits"] = credits
            r.note = f"{credits} credits"
        if not r.windows and credits is None:
            r.tier, r.error = ERROR, "no credit field in response"
        return r
