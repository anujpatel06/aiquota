"""Structured failure reasons.

Borrowed from CodexBar's plugin API, which classifies every failure instead of
returning a bare string. The difference matters: "HTTP 401" tells a user
nothing, "your API key was rejected — create a new one at platform.deepseek.com"
tells them exactly what to do next.

Each reason carries whether it's the user's problem or the provider's, and
whether retrying sooner could help. The widget uses that to decide whether to
show a fix-it hint or just a quiet dash.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Failure:
    """Why a probe failed, in terms a person can act on."""

    kind: str
    message: str
    actionable: bool          # can the user fix this themselves?
    retryable: bool           # would trying again later plausibly work?
    hint: str = ""            # what to actually do

    def __str__(self) -> str:
        return self.message


def auth_expired(service: str, fix: str = "") -> Failure:
    return Failure(
        kind="auth_expired",
        message=f"{service} rejected the credential",
        actionable=True, retryable=False,
        hint=fix or "The key or session expired — sign in again.")


def auth_missing(service: str, fix: str = "") -> Failure:
    return Failure(
        kind="auth_missing",
        message=f"No {service} credential",
        actionable=True, retryable=False,
        hint=fix or "Add one to start reading this account.")


def rate_limited(service: str, retry_after: Optional[int] = None) -> Failure:
    when = f" — retry in {retry_after}s" if retry_after else ""
    return Failure(
        kind="rate_limited",
        message=f"{service} rate-limited this check{when}",
        actionable=False, retryable=True,
        hint="aiquota will back off automatically.")


def provider_down(service: str, code: int) -> Failure:
    return Failure(
        kind="provider_down",
        message=f"{service} is having problems (HTTP {code})",
        actionable=False, retryable=True,
        hint="Nothing wrong on your side.")


def network(service: str, detail: str = "") -> Failure:
    return Failure(
        kind="network",
        message=f"Could not reach {service}",
        actionable=False, retryable=True,
        hint=detail or "Check your connection.")


def parse_failure(service: str, detail: str) -> Failure:
    """The provider answered, but not in a shape we recognise.

    Almost always means they changed their API. Worth surfacing loudly: it's
    the failure mode that silently rots undocumented endpoints.
    """
    return Failure(
        kind="parse_failure",
        message=f"{service} returned something unexpected",
        actionable=False, retryable=False,
        hint=f"{detail} — the provider likely changed their API. "
             f"Please report this.")


def classify_http(service: str, code: int, retry_after: Optional[int] = None) -> Failure:
    """Map a status code onto the right reason, so adapters don't each guess."""
    if code in (401, 403):
        return auth_expired(service)
    if code == 429:
        return rate_limited(service, retry_after)
    if code >= 500:
        return provider_down(service, code)
    return Failure(
        kind="api_failure",
        message=f"{service} returned HTTP {code}",
        actionable=False, retryable=True)
