#!/usr/bin/env python3
"""SwiftBar/xbar menu-bar renderer for aiquota."""
import json
import os
import subprocess
import sys

TIER = {"live": "●", "manual": "○", "error": "⚠", "unconfigured": "○"}


def main():
    try:
        raw = subprocess.run(
            ["aiquota", "--json", "--logos", "--ttl", "240"],
            capture_output=True, text=True, timeout=90).stdout
        data = json.loads(raw)
    except FileNotFoundError:
        print("AI ⚠")
        print("---")
        print("aiquota not installed")
        print("Get it | href=https://github.com/anujpatel06/aiquota")
        return
    except Exception as e:
        print("AI ⚠")
        print("---")
        print(f"{type(e).__name__}: {e}")
        return

    # Only show LINKED services. Unlinked platforms belong in the Add Account
    # picker, not as dead rows in the menu.
    everything = data.get("services", [])
    services = [s for s in everything if s.get("tier") != "unconfigured"]
    hidden = len(everything) - len(services)

    # Menu bar shows the single most-consumed window across everything.
    worst, _who = -1.0, ""
    for s in services:
        for w in s.get("windows", []):
            p = float(w["used_pct"])
            if p > worst:
                worst, _who = p, s.get("service", "")

    if worst < 0:
        print("AI —")
    else:
        colour = "red" if worst >= 85 else ("orange" if worst >= 60 else "")
        line = "AI %.0f%%" % worst
        print("%s | color=%s" % (line, colour) if colour else line)

    print("---")

    if not services:
        print("No accounts linked | color=#8E8E93")

    for s in services:
        mark = TIER.get(s.get("tier"), "·")
        name = s.get("service", "?")
        plan = s.get("plan") or ""
        head = "%s %s" % (mark, name)
        if plan and plan != name:
            head += " — %s" % plan
        # SwiftBar renders base64 PNGs inline via image=; show the platform
        # logo beside the name when the CLI supplied one.
        logo = s.get("logo") or ""
        if logo.startswith("data:image/png;base64,"):
            print("%s | size=13 image=%s" % (head, logo.split(",", 1)[1]))
        else:
            print("%s | size=13" % head)

        for w in s.get("windows", []):
            p = float(w["used_pct"])
            filled = int(round(p / 10))
            bar = "█" * filled + "░" * (10 - filled)
            colour = "red" if p >= 85 else ("orange" if p >= 60 else "green")
            reset = ""
            if w.get("resets_at"):
                reset = "  ↻ %s" % w["resets_at"]
            print("--%s %5.1f%%  %s%s | font=Menlo color=%s"
                  % (bar, p, w["label"], reset, colour))

        ex = s.get("extra") or {}
        if ex.get("credits") is not None:
            print("--credits: %s | font=Menlo" % ex["credits"])
        if ex.get("renews_in_days") is not None:
            print("--renews in %sd | font=Menlo" % ex["renews_in_days"])
        if s.get("error"):
            print("--%s | color=red font=Menlo" % s["error"])

    print("---")
    if hidden:
        print("%d platform%s not linked | color=#8E8E93"
              % (hidden, "" if hidden == 1 else "s"))
    # CTA: opens a native macOS list of platforms (no terminal needed).
    # NOTE: no refresh=true — SwiftBar would re-run this whole plugin (and
    # re-probe the APIs) before the window appears, adding up to a second of
    # dead time to every click. The picker refreshes on its own when it exits.
    here = os.path.dirname(os.path.abspath(__file__))
    adder = os.path.join(here, "add_account.sh")
    print("＋ Add an AI account… | color=#58a6ff terminal=false "
          "bash=%s" % adder)
    print("Refresh now | refresh=true")
    print("Open repo | href=https://github.com/anujpatel06/aiquota")


if __name__ == "__main__":
    main()
