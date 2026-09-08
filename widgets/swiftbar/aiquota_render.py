#!/usr/bin/env python3
"""SwiftBar/xbar menu-bar renderer for aiquota."""
import json
import subprocess
import sys

TIER = {"live": "●", "manual": "○", "error": "⚠", "unconfigured": "○"}


def main():
    try:
        raw = subprocess.run(
            ["aiquota", "--json", "--ttl", "240"],
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

    services = data.get("services", [])

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

    for s in services:
        mark = TIER.get(s.get("tier"), "·")
        name = s.get("service", "?")
        plan = s.get("plan") or ""
        head = "%s %s" % (mark, name)
        if plan and plan != name:
            head += " — %s" % plan
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
        # Unlinked services get a one-click way to link, instead of a dead card.
        if s.get("tier") == "unconfigured":
            print("--Link this account… | color=#58a6ff bash=/usr/bin/osascript "
                  "param1=-e param2='tell app \"Terminal\" to do script "
                  "\"aiquota link %s\"' param3=-e param4='tell app \"Terminal\" "
                  "to activate' terminal=false refresh=true" % s.get("name", ""))

    print("---")
    # Link/unlink from the menu bar itself: opens Terminal running `aiquota
    # link`, so consent is always given interactively by the user.
    print("Link an account… | bash=/usr/bin/osascript "
          "param1=-e param2='tell app \"Terminal\" to do script \"aiquota link\"' "
          "param3=-e param4='tell app \"Terminal\" to activate' "
          "terminal=false refresh=true")
    print("Refresh now | refresh=true")
    print("Open repo | href=https://github.com/anujpatel06/aiquota")


if __name__ == "__main__":
    main()
