#!/usr/bin/env python3
"""aiquota-picker — native macOS dialogs for adding an AI account.

The desktop/menu-bar widgets call this so clicking "Add account" shows a real
list of platforms, instead of dropping the user into a terminal.

Uses osascript (built into macOS) — no GUI dependency to install.
Every value written comes from the user's own choices; nothing is invented.
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from aiquota.catalog import sorted_catalog, by_key
    from aiquota.core import load_config, save_config, load_adapters, registry
except ImportError:
    # Installed as a console script — the package is on sys.path already.
    from aiquota.catalog import sorted_catalog, by_key
    from aiquota.core import load_config, save_config, load_adapters, registry

TITLE = "aiquota"


def osa(script: str) -> tuple:
    """Run AppleScript. Returns (ok, stdout). ok=False when the user cancels."""
    p = subprocess.run(["osascript", "-e", script],
                       capture_output=True, text=True)
    return p.returncode == 0, p.stdout.strip()


def q(s: str) -> str:
    """Quote for AppleScript string literals."""
    return str(s).replace("\\", "\\\\").replace('"', '\\"')


def choose(prompt: str, items, title=TITLE, default=None):
    lst = ", ".join(f'"{q(i)}"' for i in items)
    d = f' default items {{"{q(default)}"}}' if default else ""
    ok, out = osa(
        f'choose from list {{{lst}}} with title "{q(title)}" '
        f'with prompt "{q(prompt)}"{d}')
    if not ok or out in ("false", ""):
        return None
    return out


def ask(prompt: str, default="", title=TITLE):
    ok, out = osa(
        f'display dialog "{q(prompt)}" default answer "{q(default)}" '
        f'with title "{q(title)}" buttons {{"Cancel", "OK"}} '
        f'default button "OK"')
    if not ok:
        return None
    # "button returned:OK, text returned:foo"
    marker = "text returned:"
    return out.split(marker, 1)[1].strip() if marker in out else ""


def confirm(msg: str, ok_label="OK", title=TITLE):
    ok, _ = osa(
        f'display dialog "{q(msg)}" with title "{q(title)}" '
        f'buttons {{"Cancel", "{q(ok_label)}"}} default button "{q(ok_label)}"')
    return ok


def notify(msg: str, title=TITLE):
    osa(f'display notification "{q(msg)}" with title "{q(title)}"')


BADGE = {"live": "●", "soon": "◐", "manual": "○"}


def main():
    load_adapters()
    cfg = load_config()
    reg = registry()
    tracked = set(cfg.get("services", {}))

    entries = sorted_catalog()
    labels, lookup = [], {}
    for e in entries:
        mark = BADGE.get(e["support"], "·")
        state = "  ✓ added" if e["key"] in tracked else ""
        # Show what the user actually gets, right in the list.
        kind = {"live": "live usage",
                "soon": "manual for now",
                "manual": "manual entry"}.get(e["support"], "")
        label = f"{mark}  {e['name']}  —  {kind}{state}"
        labels.append(label)
        lookup[label] = e

    other = "＋  Something else…"
    labels.append(other)

    picked = choose("Which AI account do you want to add?", labels)
    if not picked:
        return 0

    # --- "Something else": user names it -------------------------------
    if picked == other:
        name = ask("What service do you want to track?\n"
                   "(e.g. NotebookLM, Ideogram, Krea)")
        if not name:
            return 0
        key = name.lower().replace(" ", "-")
        entry = {"adapter": "manual", "enabled": True,
                 "service": name.strip().title()}
        e = {"name": name, "login": "wherever it shows your usage"}
        return finish_manual(cfg, key, entry, e)

    e = lookup[picked]
    key = e["key"]

    # --- live platforms: look for a credential, then ASK ---------------
    if e["support"] == "live":
        ad = reg.get(e["adapter"])
        found = []
        if ad:
            try:
                found = ad.detect() or []
            except Exception:
                found = []
        if not found:
            confirm(f"No {e['name']} credential found on this Mac.\n\n"
                    f"Set it up first:\n{e['login']}\n\n"
                    "Then open this again.", ok_label="OK")
            return 0
        f = found[0]
        cost = f"\n\nNote: {ad.cost_note}" if ad and ad.cost_note else ""
        if not confirm(f"Link {e['name']}?\n\n"
                       f"aiquota will read:\n{f['source']}\n\n"
                       f"{f['detail']}{cost}", ok_label="Link"):
            return 0
        entry = cfg["services"].get(key, {})
        entry.update({"adapter": e["adapter"], "enabled": True})
        entry.update(f.get("config") or {})
        plan = ask(f"Plan label for {e['name']}? (optional)", "")
        if plan:
            entry["plan"] = plan
        cfg["services"][key] = entry
        save_config(cfg)
        notify(f"Linked {e['name']}")
        return 0

    # --- manual platforms: the user supplies the numbers ---------------
    entry = {"adapter": "manual", "enabled": True, "service": e["name"]}
    return finish_manual(cfg, key, entry, e)


def finish_manual(cfg, key, entry, e):
    """Collect user-entered values. Anything skipped stays empty — never guessed."""
    name = e["name"]
    login = e.get("login", "")
    if not confirm(f"{name} has no usage API.\n\n"
                   f"Check your balance here:\n{login}\n\n"
                   "Then enter what you see. Leave blank to skip.",
                   ok_label="Continue"):
        return 0

    plan = ask(f"{name} — plan label? (optional)", "")
    if plan is None:
        return 0
    credits = ask(f"{name} — credits/units REMAINING?\n(leave blank to skip)", "")
    if credits is None:
        return 0
    total = ask(f"{name} — total per period?\n(leave blank to skip)", "")
    if total is None:
        return 0
    renews = ask(f"{name} — renews on? YYYY-MM-DD\n(leave blank to skip)", "")
    if renews is None:
        return 0

    import time
    if plan:
        entry["plan"] = plan
    for field, raw in (("credits", credits), ("credits_total", total)):
        if raw:
            try:
                entry[field] = float(raw) if "." in raw else int(raw)
            except ValueError:
                entry[field] = raw
    if renews:
        entry["renews_on"] = renews
    if not credits and not renews:
        entry["note"] = "Added — no values entered yet"
    entry["updated"] = time.strftime("%Y-%m-%d")

    cfg["services"][key] = entry
    save_config(cfg)
    notify(f"Added {name}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
