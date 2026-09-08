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
    from aiquota.core import (load_config, save_config, load_adapters,
                              registry, linked_services)
except ImportError:
    # Installed as a console script — the package is on sys.path already.
    from aiquota.catalog import sorted_catalog, by_key
    from aiquota.core import (load_config, save_config, load_adapters,
                              registry, linked_services)

TITLE = "aiquota"


class DialogError(RuntimeError):
    """A dialog failed for a reason that is NOT the user cancelling."""


def osa(script: str) -> tuple:
    """Run AppleScript through Finder. Returns (ok, stdout); ok=False on cancel.

    WHY FINDER: when osascript runs from a non-GUI process (a SwiftBar plugin,
    an Übersicht `run()`, a background shell) it has no window-server access,
    so `choose from list` and `display dialog` resolve INSTANTLY with a default
    answer instead of showing anything — the button appears to do nothing.
    Verified: bare, `tell System Events`, `tell me`, and `launchctl asuser` all
    auto-answer. Addressing Finder, which always owns a GUI session, is what
    actually puts a window on screen.

    Raises DialogError for real failures (permissions, syntax) so they are
    never silently misread as "the user cancelled".
    """
    wrapped = ('tell application "Finder"\n'
               '  activate\n'
               f'  {script}\n'
               'end tell')
    p = subprocess.run(["osascript", "-e", wrapped],
                       capture_output=True, text=True)
    if p.returncode == 0:
        return True, p.stdout.strip()

    err = (p.stderr or "").strip()
    # -128 is the documented "User canceled" code; osascript also emits the
    # phrase for Cancel buttons. Everything else is a genuine error.
    if "-128" in err or "User canceled" in err or "user cancelled" in err.lower():
        return False, ""
    raise DialogError(err or f"osascript exited {p.returncode}")


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


def ask(prompt: str, default="", title=TITLE, hidden=False):
    hid = " with hidden answer" if hidden else ""
    ok, out = osa(
        f'display dialog "{q(prompt)}" default answer "{q(default)}" '
        f'with title "{q(title)}" buttons {{"Cancel", "OK"}} '
        f'default button "OK"{hid}')
    if not ok:
        return None
    # "button returned:OK, text returned:foo"
    marker = "text returned:"
    return out.split(marker, 1)[1].strip() if marker in out else ""


def ask_form(title, prompt, fields):
    """Collect several values in ONE dialog instead of a prompt chain.

    `fields` is a list of (key, label). The user types comma-separated values
    on a single line — four modal dialogs in a row is a terrible experience,
    and the earlier version of this tool did exactly that.
    Returns {key: value} with blanks omitted, or None if cancelled.
    """
    labels = ", ".join(label for _, label in fields)
    raw = ask(f"{prompt}\n\nEnter, separated by commas:\n{labels}\n"
              "(leave any part blank to skip)", "", title)
    if raw is None:
        return None
    parts = [p.strip() for p in raw.split(",")]
    out = {}
    for i, (key, _label) in enumerate(fields):
        if i < len(parts) and parts[i]:
            out[key] = parts[i]
    return out


def confirm(msg: str, ok_label="OK", title=TITLE):
    ok, _ = osa(
        f'display dialog "{q(msg)}" with title "{q(title)}" '
        f'buttons {{"Cancel", "{q(ok_label)}"}} default button "{q(ok_label)}"')
    return ok


def notify(msg: str, title=TITLE):
    osa(f'display notification "{q(msg)}" with title "{q(title)}"')


BADGE = {"live": "●", "soon": "◐", "manual": "○"}


def main():
    try:
        return _main()
    except KeyboardInterrupt:
        return 130
    except DialogError as e:
        msg = str(e)[:180]
        print(f"aiquota-picker: dialog failed: {msg}", file=sys.stderr)
        try:
            subprocess.run(
                ["osascript", "-e",
                 f'display notification "{q(msg)}" with title "aiquota — error"'],
                capture_output=True, text=True, timeout=10)
        except Exception:
            pass
        return 1


def _main():
    load_adapters()
    cfg = load_config()
    reg = registry()
    # 'added' must mean genuinely LINKED — a bare config entry is not.
    tracked = linked_services(cfg)

    entries = sorted_catalog()

    # Rich HTML picker (logos + status pills). Falls back to the plain
    # AppleScript list if anything about the GUI path fails.
    picked_key = None
    try:
        from .guipick import choose_gui
        picked_key = choose_gui(entries, tracked)
        if picked_key is None:
            return 0                      # cancelled
    except Exception:
        picked_key = None

    if picked_key == "__other__":
        name = ask("What service do you want to track?\n"
                   "(e.g. NotebookLM, Ideogram, Krea)")
        if not name:
            return 0
        key = name.lower().replace(" ", "-")
        entry = {"adapter": "manual", "enabled": True,
                 "service": name.strip().title()}
        e = {"name": name.strip().title(),
             "login": "wherever it shows your usage"}
        return finish_manual(cfg, key, entry, e)

    if picked_key:
        e = by_key(picked_key)
        if e:
            return _handle_choice(cfg, reg, e)

    # ---- fallback: plain AppleScript list --------------------------------
    labels, lookup = [], {}
    for e in entries:
        mark = BADGE.get(e["support"], "·")
        state = "  ✓ added" if e["key"] in tracked else ""
        kind = {"live": "live usage", "soon": "manual for now",
                "manual": "manual entry"}.get(e["support"], "")
        label = f"{mark}  {e['name']}  —  {kind}{state}"
        labels.append(label)
        lookup[label] = e

    other = "＋  Something else…"
    labels.append(other)

    picked = choose("Which AI account do you want to add?", labels)
    if not picked:
        return 0

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

    return _handle_choice(cfg, reg, lookup[picked])


def _handle_choice(cfg, reg, e):
    """Route a chosen catalog entry to the right linking flow."""
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

    # --- browser sign-in (OAuth) if the platform supports it -----------
    ad = reg.get(e["adapter"])
    if ad is not None and getattr(ad, "oauth_login", None):
        return finish_oauth(cfg, key, e, ad)

    # --- API-key platforms: one paste, then live forever ---------------
    if ad is not None and getattr(ad, "api_key_label", None):
        return finish_api_key(cfg, key, e, ad)

    # --- manual platforms: the user supplies the numbers ---------------
    entry = {"adapter": "manual", "enabled": True, "service": e["name"]}
    return finish_manual(cfg, key, entry, e)


def finish_oauth(cfg, key, e, ad):
    """Open the platform's own login page in the browser. No key pasting."""
    from . import oauth as oauth_mod

    name = e["name"]
    label = getattr(ad, "oauth_label", f"Sign in to {name}")
    if not confirm(f"{label}\n\n"
                   "Your browser will open so you can sign in on "
                   f"{name}'s own site.\n"
                   "aiquota never sees your password.",
                   ok_label="Open browser"):
        return 0

    fn = getattr(oauth_mod, f"{ad.oauth_login}_login", None)
    if fn is None:
        confirm(f"No sign-in flow available for {name}.", ok_label="OK")
        return 0

    token, err = fn()
    if err:
        confirm(f"Sign-in failed.\n\n{err}\n\n{name} was not added.",
                ok_label="OK")
        return 0

    probe = ad.probe({"api_key": token})
    if probe.tier != "live":
        confirm(f"Signed in, but the check failed.\n\n"
                f"{probe.error or 'unknown error'}", ok_label="OK")
        return 0

    entry = cfg["services"].get(key, {})
    entry.update({"adapter": ad.name, "enabled": True, "api_key": token,
                  "auth": "oauth"})
    cfg["services"][key] = entry
    save_config(cfg)

    detail = ""
    if probe.windows:
        w = probe.windows[0]
        detail = f"\n\n{w.label}: {w.used_pct:.0f}% used"
    elif probe.extra.get("spent"):
        detail = f"\n\nSpent: {probe.extra['spent']}"
    notify(f"Connected {name}")
    confirm(f"✓ {name} connected.{detail}", ok_label="Done")
    return 0


def finish_api_key(cfg, key, e, ad):
    """Ask once for an API key, verify it, then usage is fetched live."""
    name = e["name"]
    paste = ask(f"{name} — paste your API key\n\n"
                f"Get one here:\n{ad.api_key_help}\n\n"
                "It is stored locally in your config (chmod 600).",
                "", TITLE, hidden=True)
    if paste is None:
        return 0
    paste = paste.strip()
    if not paste:
        confirm(f"No key entered — {name} was not added.", ok_label="OK")
        return 0

    # Verify before saving, so a bad key fails here and not silently later.
    probe = ad.probe({"api_key": paste})
    if probe.tier != "live":
        confirm(f"That key didn't work.\n\n{probe.error or 'unknown error'}\n\n"
                f"{name} was not added.", ok_label="OK")
        return 0

    entry = cfg["services"].get(key, {})
    entry.update({"adapter": ad.name, "enabled": True, "api_key": paste})
    cfg["services"][key] = entry
    save_config(cfg)

    detail = ""
    if probe.windows:
        w = probe.windows[0]
        detail = f"\n\n{w.label}: {w.used_pct:.0f}% used"
    notify(f"Linked {name}")
    confirm(f"✓ {name} linked and verified.{detail}", ok_label="Done")
    return 0


def finish_manual(cfg, key, entry, e):
    """Collect user-entered values in ONE dialog. Skipped fields stay empty —
    never guessed."""
    import time
    name = e["name"]
    login = e.get("login", "")

    vals = ask_form(
        TITLE,
        f"{name} has no usage API, so you enter the numbers.\n"
        f"Check yours at: {login}",
        [("plan", "plan"), ("credits", "remaining"),
         ("credits_total", "total"), ("renews_on", "renews YYYY-MM-DD")])
    if vals is None:
        return 0

    if vals.get("plan"):
        entry["plan"] = vals["plan"]
    for field in ("credits", "credits_total"):
        raw = vals.get(field)
        if raw:
            try:
                entry[field] = float(raw) if "." in raw else int(raw)
            except ValueError:
                entry[field] = raw
    if vals.get("renews_on"):
        entry["renews_on"] = vals["renews_on"]
    if not vals.get("credits") and not vals.get("renews_on"):
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
    except DialogError as e:
        # Never fail silently: a widget button that does nothing is the worst
        # possible outcome. Report on stderr AND as a notification.
        msg = str(e)[:180]
        print(f"aiquota-picker: dialog failed: {msg}", file=sys.stderr)
        try:
            subprocess.run(
                ["osascript", "-e",
                 f'display notification "{q(msg)}" with title "aiquota — error"'],
                capture_output=True, text=True, timeout=10)
        except Exception:
            pass
        sys.exit(1)
