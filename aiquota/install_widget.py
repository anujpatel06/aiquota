"""`aiquota install-widget` — put the desktop/menu-bar widgets in place.

Why this exists
---------------
`pip install aiquota` gave you a CLI and nothing else. The widgets lived only
in the git repo, so the actual instructions were "clone the repo, copy four
files into two different directories, chmod one of them, then restart two
apps". Nobody does that, and anyone who tried on a released version would find
the files simply absent.

The widget sources now ship inside the package, and this command copies them
where SwiftBar and Übersicht look, reports what it did, and says plainly when
a host app is missing rather than leaving a file somewhere hopeful.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "widgets")

UBERSICHT_DIR = os.path.expanduser(
    "~/Library/Application Support/Übersicht/widgets")
SWIFTBAR_DIR = os.path.expanduser("~/.local/share/swiftbar")

UBERSICHT_APP = "/Applications/Übersicht.app"
SWIFTBAR_APP = "/Applications/SwiftBar.app"


def _copy(src_name: str, dest_dir: str, executable: bool = False) -> str:
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, src_name)
    shutil.copyfile(os.path.join(SRC, src_name), dest)
    if executable:
        os.chmod(dest, 0o755)
    return dest


def install_ubersicht() -> Tuple[bool, str]:
    if not os.path.exists(UBERSICHT_APP):
        return False, ("Übersicht isn't installed — "
                       "brew install --cask ubersicht")
    dest = _copy("aiquota.jsx", UBERSICHT_DIR)
    return True, dest


def install_swiftbar() -> Tuple[bool, str]:
    if not os.path.exists(SWIFTBAR_APP):
        return False, "SwiftBar isn't installed — brew install --cask swiftbar"
    _copy("aiquota_render.py", SWIFTBAR_DIR)
    _copy("add_account.sh", SWIFTBAR_DIR, executable=True)
    dest = _copy("aiquota.5m.sh", SWIFTBAR_DIR, executable=True)

    # SwiftBar launches plugins with a bare PATH, and the hard-coded guesses
    # in the script only cover ~/.local/bin and Homebrew. A pipx or venv
    # install lives elsewhere, so record where THIS aiquota actually is.
    bindir = os.path.dirname(os.path.abspath(sys.argv[0]))
    for name in ("aiquota.5m.sh", "add_account.sh"):
        path = os.path.join(SWIFTBAR_DIR, name)
        try:
            with open(path) as f:
                body = f.read()
            marked = body.replace(
                'export PATH="$HOME/.local/bin:',
                f'export PATH="{bindir}:$HOME/.local/bin:', 1).replace(
                'PATH="$HOME/.local/bin:',
                f'PATH="{bindir}:$HOME/.local/bin:', 1)
            if marked != body:
                with open(path, "w") as f:
                    f.write(marked)
                os.chmod(path, 0o755)
        except OSError:
            pass

    # SwiftBar only reads one folder, and it is set in preferences rather
    # than by convention — point it here if the user hasn't chosen one.
    try:
        cur = subprocess.run(
            ["defaults", "read", "com.ambar.SwiftBar", "PluginDirectory"],
            capture_output=True, text=True, timeout=5).stdout.strip()
        if not cur:
            subprocess.run(
                ["defaults", "write", "com.ambar.SwiftBar",
                 "PluginDirectory", "-string", SWIFTBAR_DIR],
                capture_output=True, timeout=5)
    except Exception:
        pass
    return True, dest


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if sys.platform != "darwin":
        print("aiquota's widgets are macOS-only (SwiftBar and Übersicht).\n"
              "The CLI works everywhere: run `aiquota`.", file=sys.stderr)
        return 1

    if not os.path.isdir(SRC):
        print("aiquota: widget files are missing from this install.\n"
              "Reinstall with: pip install --force-reinstall aiquota",
              file=sys.stderr)
        return 1

    want = [a for a in argv if not a.startswith("-")]
    do_bar = not want or "menubar" in want or "swiftbar" in want
    do_desk = not want or "desktop" in want or "ubersicht" in want

    installed, missing = [], []
    if do_bar:
        ok, msg = install_swiftbar()
        (installed if ok else missing).append(("Menu bar (SwiftBar)", msg))
    if do_desk:
        ok, msg = install_ubersicht()
        (installed if ok else missing).append(("Desktop (Übersicht)", msg))

    for label, dest in installed:
        print(f"  installed  {label}\n             {dest}")
    for label, why in missing:
        print(f"  skipped    {label}\n             {why}")

    if installed:
        # A freshly copied plugin isn't picked up until the host app looks
        # again; restarting is the reliable way to make it appear now.
        for app in ("SwiftBar", "Übersicht"):
            if any(app.lower() in lbl.lower() or
                   (app == "Übersicht" and "Desktop" in lbl)
                   for lbl, _ in installed):
                subprocess.run(["open", "-ga", app],
                               capture_output=True, timeout=10)
        print("\nDone. Add an account from the widget, "
              "or run: aiquota link")
    if missing and not installed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
