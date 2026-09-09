"""How often to re-check, based on whether anyone is looking.

Borrowed from CodexBar's AdaptiveRefreshPolicyCore. The insight is that a
fixed refresh interval is wrong in both directions: too slow while you're
working and watching your quota drain, too fast when the laptop is shut in a
bag on battery.

Their published table, which this mirrors:

    just interacted   2 min      you opened the widget; you're watching
    coding activity   5 min cap  a session is running, quota is moving
    warm              5 min      recent, but not right now
    idle             15 min      nobody has looked in a while
    long idle        30 min      nobody has looked in a long while
    constrained      30 min      low power mode or thermal pressure

The point isn't the exact numbers, it's that polling a provider every minute
while the user is asleep is rude to them and to the provider — and it's the
kind of traffic that gets undocumented endpoints closed.
"""
from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from typing import Optional

RECENT_INTERACTION = 2 * 60
CODING_ACTIVITY_CAP = 5 * 60
WARM = 5 * 60
IDLE = 15 * 60
LONG_IDLE = 30 * 60
CONSTRAINED = 30 * 60

# Boundaries for classifying "how long since someone looked".
_WARM_AFTER = 5 * 60
_IDLE_AFTER = 30 * 60


@dataclass(frozen=True)
class Decision:
    delay: int          # seconds until the next check
    reason: str         # why, so `aiquota doctor` can explain itself

    @property
    def human(self) -> str:
        m = self.delay // 60
        return f"every {m} min ({self.reason.replace('_', ' ')})"


def low_power_mode() -> bool:
    """True when macOS Low Power Mode is on.

    Reading quota is never urgent enough to fight the battery setting the user
    explicitly chose.
    """
    if os.environ.get("AIQUOTA_ASSUME_LOW_POWER") == "1":
        return True
    try:
        out = subprocess.run(["pmset", "-g"], capture_output=True, text=True,
                             timeout=3).stdout
    except Exception:
        return False
    for line in out.splitlines():
        if "lowpowermode" in line.replace(" ", "").lower():
            return line.strip().endswith("1")
    return False


def decide(now: Optional[float] = None,
           last_seen_at: Optional[float] = None,
           coding_active: bool = False,
           constrained: Optional[bool] = None) -> Decision:
    """Pick a refresh delay.

    `last_seen_at` is when the user last opened the widget or ran the CLI.
    `coding_active` means an agent session is burning quota right now, so the
    number on screen goes stale fast even if nobody just clicked.
    """
    now = time.time() if now is None else now
    if constrained is None:
        constrained = low_power_mode()

    if constrained:
        return Decision(CONSTRAINED, "constrained")

    since = None if last_seen_at is None else max(0.0, now - last_seen_at)

    if since is not None and since < RECENT_INTERACTION:
        return Decision(RECENT_INTERACTION, "recent_interaction")
    if coding_active:
        return Decision(CODING_ACTIVITY_CAP, "coding_activity")
    if since is None:
        return Decision(LONG_IDLE, "long_idle")
    if since < _WARM_AFTER:
        return Decision(WARM, "warm")
    if since < _IDLE_AFTER:
        return Decision(IDLE, "idle")
    return Decision(LONG_IDLE, "long_idle")


def touch(path: str) -> None:
    """Record that the user just looked. Cheap and best-effort."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(str(time.time()))
    except Exception:
        pass


def last_seen(path: str) -> Optional[float]:
    try:
        with open(path) as f:
            return float(f.read().strip())
    except Exception:
        return None
