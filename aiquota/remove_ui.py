"""Remove a tracked service, with a confirmation dialog.

Exists as its own console script for one reason: building nested AppleScript
inside a JavaScript string inside a shell command — which is what the desktop
widget was doing — is unshippable. Every layer needs its own escaping, and the
click log showed the quoting collapsing before it ever reached osascript:

    tell application Finder to display dialog Remove claude from aiquota? ...
                            ^ quotes gone — not valid AppleScript

The widget now calls `aiquota-remove <service>` with a single plain argument,
and the dialog is drawn by the same picker.confirm() that the Add flow already
uses successfully.
"""
from __future__ import annotations

import os
import sys

from .core import load_config, save_config
from .picker import confirm, notify, DialogError


def remove(name: str, ask: bool = True) -> int:
    cfg = load_config()
    services = cfg.get("services") or {}
    if name not in services:
        notify(f"{name} is not tracked")
        return 1

    label = services[name].get("service") or name
    if ask and not confirm(f"Remove {label} from aiquota?\n\n"
                           "Its usage card disappears from the widget. "
                           "Nothing is changed on the provider's side, and "
                           "you can add it again at any time.",
                           ok_label="Remove"):
        return 0

    del services[name]
    cfg["services"] = services
    save_config(cfg)

    # Drop any cached reading so the widget doesn't redraw a removed card.
    try:
        from .core import _read_cache, _write_cache
        cache = _read_cache()
        if name in cache:
            del cache[name]
            _write_cache(cache)
    except Exception:
        pass

    _refresh_widgets()
    notify(f"Removed {label}")
    return 0


def _refresh_widgets() -> None:
    """Make the desktop widget redraw now instead of at its next tick.

    Übersicht re-runs a widget's `command` on `refreshFrequency` — five
    minutes here. Without a nudge the card you just deleted sits on screen
    until then, which reads as "remove is broken". Touching the .jsx makes
    Übersicht reload it immediately; SwiftBar reloads via its URL scheme.
    """
    import subprocess
    jsx = os.path.expanduser(
        "~/Library/Application Support/Übersicht/widgets/aiquota.jsx")
    if os.path.exists(jsx):
        try:
            os.utime(jsx, None)
        except OSError:
            pass
    try:
        subprocess.run(["open", "-g", "swiftbar://refreshallplugins"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=5)
    except Exception:
        pass


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: aiquota-remove <service> [--yes]", file=sys.stderr)
        return 2
    name = argv[0]
    ask = "--yes" not in argv and "-y" not in argv
    try:
        return remove(name, ask=ask)
    except DialogError as exc:
        print(f"aiquota-remove: dialog failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
