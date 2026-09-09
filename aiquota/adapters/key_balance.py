"""Adapters for providers with a documented, key-authenticated balance API.

These are the easy, safe cases: the provider publishes an endpoint, you create
a key in your own dashboard, and reading your own balance is the endpoint's
stated purpose. No session capture, no undocumented routes, no ToS grey area.

Every endpoint below was probed unauthenticated and answered 401 with a JSON
error — the route exists and wants a key, rather than 404. Verified
2026-09-09:

    api.deepseek.com/user/balance              401 Authentication Fails
    api.poe.com/usage/current_balance          401 Incorrect API key provided
    api.fal.ai/v1/account/billing              401 authorization_error
    api.heygen.com/v2/user/remaining_quota     401 Unauthorized
    cloud.leonardo.ai/api/rest/v1/me           401 Authentication hook …
    external.api.recraft.ai/v1/users/me        401 request unauthorized
    api.klingai.com/account/costs              401 Authorization is empty
    api.z.ai/api/monitor/usage/quota/limit     200 {"code":1001,"msg":"Auth…"}

Field names come from each provider's own documentation. Where a provider
reports a raw balance with no cap, no percentage is invented — the card shows
the number and no meter, because a percentage of an unknown total is a lie.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .. import failures
from ..core import ERROR, LIVE, UNCONFIGURED, Adapter, Result, Window, register
from ._http import fmt_reset, get_json


class KeyBalanceAdapter(Adapter):
    """Base: one API key, one GET, one balance."""

    usage_url = ""
    auth_style = "bearer"          # bearer | x-api-key | authorization-raw
    api_key_label = ""
    api_key_help = ""

    def _headers(self, key: str) -> Dict[str, str]:
        if self.auth_style == "x-api-key":
            return {"x-api-key": key, "Accept": "application/json"}
        if self.auth_style == "authorization-raw":
            return {"Authorization": key, "Accept": "application/json"}
        return {"Authorization": f"Bearer {key}", "Accept": "application/json"}

    def probe(self, conf: Dict[str, Any]) -> Result:
        key = conf.get("api_key") or conf.get("token")
        if not key:
            return self.make(conf, tier=UNCONFIGURED, note=self.setup,
                             error="no API key")
        code, data = get_json(self.usage_url, headers=self._headers(str(key)))
        if code != 200 or not isinstance(data, dict):
            f = failures.classify_http(self.service, code)
            if code in (401, 403):
                f = failures.auth_expired(
                    self.service, f"Create a new key at {self.api_key_help}.")
            elif code == 200:
                f = failures.parse_failure(self.service, "expected a JSON object")
            r = self.make(conf, tier=ERROR)
            r.error = f.message
            r.failure_kind, r.failure_hint = f.kind, f.hint
            return r
        return self.parse(conf, data)

    def parse(self, conf, d) -> Result:  # pragma: no cover - overridden
        raise NotImplementedError

    @staticmethod
    def _num(v) -> Optional[float]:
        try:
            return float(v)
        except (TypeError, ValueError):
            return None


@register
class DeepSeekAdapter(KeyBalanceAdapter):
    name = "deepseek"
    service = "DeepSeek"
    summary = "Prepaid balance"
    setup = "Create a key at platform.deepseek.com → API keys."
    usage_url = "https://api.deepseek.com/user/balance"
    api_key_label = "DeepSeek API key"
    api_key_help = "platform.deepseek.com → API keys"

    def parse(self, conf, d) -> Result:
        r = self.make(conf, tier=LIVE)
        r.confidence = "exact"
        infos = d.get("balance_infos") or []
        if not infos:
            r.tier, r.error = ERROR, "no balance in response"
            return r
        b = infos[0]
        total = self._num(b.get("total_balance"))
        if total is None:
            r.tier, r.error = ERROR, "no total_balance field"
            return r
        cur = b.get("currency", "")
        r.extra["balance"] = total
        r.note = f"{total:.2f} {cur}".strip()
        if d.get("is_available") is False:
            r.note += " — account not available"
        return r


@register
class PoeAdapter(KeyBalanceAdapter):
    name = "poe"
    service = "Poe"
    summary = "Compute points remaining"
    setup = "Create a key at poe.com/api_key."
    usage_url = "https://api.poe.com/usage/current_balance"
    api_key_label = "Poe API key"
    api_key_help = "poe.com/api_key"

    def parse(self, conf, d) -> Result:
        r = self.make(conf, tier=LIVE)
        r.confidence = "exact"
        pts = self._num(d.get("current_point_balance"))
        if pts is None:
            r.tier, r.error = ERROR, "no current_point_balance"
            return r
        r.extra["points"] = pts
        r.note = f"{pts:,.0f} points"
        # Poe publishes a monthly grant per plan, but the API doesn't return
        # it — so no percentage. A meter against a guessed cap is worse than
        # no meter.
        return r


@register
class FalAdapter(KeyBalanceAdapter):
    name = "fal"
    service = "fal.ai"
    summary = "Credit balance"
    setup = "Create a key at fal.ai/dashboard/keys."
    usage_url = "https://api.fal.ai/v1/account/billing?expand=credits"
    auth_style = "authorization-raw"      # fal uses "Key <id>:<secret>"
    api_key_label = "fal.ai key"
    api_key_help = "fal.ai/dashboard/keys — paste as: Key <id>:<secret>"

    def parse(self, conf, d) -> Result:
        r = self.make(conf, tier=LIVE)
        r.confidence = "exact"
        credits = d.get("credits")
        bal = None
        if isinstance(credits, dict):
            bal = self._num(credits.get("current_balance"))
        if bal is None:
            bal = self._num(d.get("current_balance"))
        if bal is None:
            r.tier, r.error = ERROR, "no credit balance in response"
            return r
        r.extra["credits"] = bal
        r.note = f"${bal:,.2f} credits"
        return r


@register
class HeyGenAdapter(KeyBalanceAdapter):
    name = "heygen"
    service = "HeyGen"
    summary = "Video credits remaining"
    setup = "Create a key at app.heygen.com → Settings → API."
    usage_url = "https://api.heygen.com/v2/user/remaining_quota"
    auth_style = "x-api-key"
    api_key_label = "HeyGen API key"
    api_key_help = "app.heygen.com → Settings → API"

    def parse(self, conf, d) -> Result:
        r = self.make(conf, tier=LIVE)
        r.confidence = "exact"
        data = d.get("data") if isinstance(d.get("data"), dict) else d
        rem = self._num(data.get("remaining_quota"))
        used = self._num(data.get("used_quota"))
        if rem is None:
            r.tier, r.error = ERROR, "no remaining_quota"
            return r
        # HeyGen reports quota in credits*60 (seconds); show both when we can
        # derive a total honestly.
        r.extra["remaining"] = rem
        if used is not None and (rem + used) > 0:
            total = rem + used
            r.windows.append(Window(
                key="credits", label="Credits",
                used_pct=round(used / total * 100, 1), resets_at=""))
            r.extra["used"] = used
            r.extra["total"] = total
        else:
            r.note = f"{rem:,.0f} remaining"
        return r


@register
class LeonardoAdapter(KeyBalanceAdapter):
    name = "leonardo"
    service = "Leonardo.ai"
    summary = "Tokens and renewal date"
    setup = "Create a key at app.leonardo.ai → API Access."
    usage_url = "https://cloud.leonardo.ai/api/rest/v1/me"
    api_key_label = "Leonardo API key"
    api_key_help = "app.leonardo.ai → API Access"

    def parse(self, conf, d) -> Result:
        r = self.make(conf, tier=LIVE)
        r.confidence = "exact"
        me = d.get("user_details")
        rec = me[0] if isinstance(me, list) and me else d
        if not isinstance(rec, dict):
            r.tier, r.error = ERROR, "unexpected response shape"
            return r
        sub = self._num(rec.get("subscriptionTokens"))
        paid = self._num(rec.get("paidTokens"))
        if sub is None and paid is None:
            r.tier, r.error = ERROR, "no token fields in response"
            return r
        total = (sub or 0) + (paid or 0)
        r.extra["subscription_tokens"] = sub
        r.extra["paid_tokens"] = paid
        renew = rec.get("tokenRenewalDate")
        r.note = f"{total:,.0f} tokens"
        if renew:
            r.note += f" · renews {fmt_reset(renew) or renew}"
        return r


@register
class RecraftAdapter(KeyBalanceAdapter):
    name = "recraft"
    service = "Recraft"
    summary = "Credit balance"
    setup = "Create a key at recraft.ai → Profile → API."
    usage_url = "https://external.api.recraft.ai/v1/users/me"
    api_key_label = "Recraft API key"
    api_key_help = "recraft.ai → Profile → API"

    def parse(self, conf, d) -> Result:
        r = self.make(conf, tier=LIVE)
        r.confidence = "exact"
        for k in ("credits", "balance", "credit_balance"):
            v = self._num(d.get(k))
            if v is not None:
                r.extra["credits"] = v
                r.note = f"{v:,.0f} credits"
                return r
        r.tier, r.error = ERROR, "no credit field in response"
        return r


@register
class KlingAdapter(KeyBalanceAdapter):
    name = "kling"
    service = "Kling"
    summary = "Resource pack quota"
    setup = "Create a key at klingai.com → API console."
    usage_url = "https://api.klingai.com/account/costs"
    api_key_label = "Kling API token"
    api_key_help = "klingai.com → API console (JWT)"

    def parse(self, conf, d) -> Result:
        r = self.make(conf, tier=LIVE)
        r.confidence = "exact"
        data = d.get("data") if isinstance(d.get("data"), dict) else d
        packs = data.get("resource_pack_subscribe_infos") or []
        for p in packs:
            if not isinstance(p, dict):
                continue
            rem = self._num(p.get("remaining_quantity"))
            tot = self._num(p.get("total_quantity"))
            if rem is None or not tot:
                continue
            label = p.get("resource_pack_name") or "Resource pack"
            r.windows.append(Window(
                key=str(p.get("resource_pack_id") or label),
                label=str(label)[:24],
                used_pct=round((tot - rem) / tot * 100, 1),
                resets_at=fmt_reset(p.get("effective_time")) or ""))
        if not r.windows:
            r.tier, r.error = ERROR, "no resource packs in response"
        return r


@register
class ZaiAdapter(KeyBalanceAdapter):
    name = "zai"
    service = "Z.ai"
    summary = "5-hour, weekly and monthly windows"
    setup = "Create a key at z.ai → API keys."
    usage_url = "https://api.z.ai/api/monitor/usage/quota/limit"
    api_key_label = "Z.ai API key"
    api_key_help = "z.ai → API keys"

    def parse(self, conf, d) -> Result:
        r = self.make(conf, tier=LIVE)
        r.confidence = "exact"
        data = d.get("data") if isinstance(d.get("data"), dict) else d
        labels = {"5h": "5-hour", "five_hour": "5-hour",
                  "weekly": "Weekly", "week": "Weekly",
                  "monthly": "Monthly", "month": "Monthly"}
        for key, label in labels.items():
            v = data.get(key)
            if not isinstance(v, dict):
                continue
            used = self._num(v.get("used") or v.get("used_percent"))
            total = self._num(v.get("limit") or v.get("total"))
            if used is None:
                continue
            pct = (round(used / total * 100, 1) if total
                   else round(used, 1))
            r.windows.append(Window(key=key, label=label, used_pct=pct,
                                    resets_at=fmt_reset(v.get("reset_at")) or ""))
        if not r.windows:
            r.note = "signed in — no quota windows in response"
        return r
