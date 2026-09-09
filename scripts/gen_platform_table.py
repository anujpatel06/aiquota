#!/usr/bin/env python3
"""Rewrite the README's platform table from the actual catalog + policy.

Hand-maintained tables drift. This generates the section from the same data
the picker uses, so the docs can't claim support that doesn't exist.
"""
import pathlib, sys
sys.path.insert(0, "/Users/anujpatel/projects/aiquota")
from aiquota.catalog import sorted_catalog
from aiquota.login_policy import policy_for

browser, cred, manual = [], [], []
for e in sorted_catalog():
    pol, why, src = policy_for(e["key"])
    (browser if pol == "browser" else
     cred if pol == "own-credential" else manual).append((e, why, src))

lines = ["## Supported platforms", "",
         "How you connect each one depends on what the provider allows.", ""]

lines += ["### Sign in with your account", "",
          "Click the platform, its own login page opens, you pick the account.",
          "No API key, no password shown to aiquota.", "",
          "| Platform | What you get |", "|---|---|"]
for e, _why, _src in browser:
    lines.append(f"| **{e['name']}** | {e.get('note','')} |")

lines += ["", "### Uses a credential you already have", "",
          "These providers restrict third-party sign-in, so aiquota reads a",
          "credential you created yourself — and asks first.", "",
          "| Platform | Why not sign-in | Source |", "|---|---|---|"]
for e, why, src in cred:
    short = why.split(".")[0] + "."
    host = src.split("//")[-1].split("/")[0] if src else ""
    link = f"[{host}]({src})" if src else "—"
    lines.append(f"| **{e['name']}** | {short} | {link} |")

lines += ["", "### Manual entry", ""]

# Split the manual bucket: "no endpoint" is a very different statement from
# "the provider forbids reading it", and collapsing them would hide the more
# important one.
refused = [(e, w, s) for e, w, s in manual
           if "prohibit" in w.lower() or "forbid" in w.lower()]
absent = [(e, w, s) for e, w, s in manual if (e, w, s) not in refused]

if absent:
    lines += ["No reachable usage endpoint — probed and confirmed, not assumed.",
              "You enter the numbers and they're labelled `manual`.", "",
              ", ".join(f"**{e['name']}**" for e, _w, _s in absent) + ".", ""]

if refused:
    lines += ["#### Deliberately not read", "",
              "These have working endpoints. aiquota refuses to use them,",
              "because the provider prohibits automated access and enforces it.",
              "A quota number isn't worth someone's account.", "",
              "| Platform | Why | Source |", "|---|---|---|"]
    for e, why, src in refused:
        host = src.split("//")[-1].split("/")[0] if src else ""
        link = f"[{host}]({src})" if src else "—"
        lines.append(f"| **{e['name']}** | {why} | {link} |")
    lines.append("")

lines += ["Anything not listed: choose \"Something else…\" in the picker.",
          "",
          "If you know a real endpoint for a manual entry, that's the most",
          "valuable PR you can send — see [CONTRIBUTING.md](CONTRIBUTING.md).",
          ""]

section = "\n".join(lines)

p = pathlib.Path("/Users/anujpatel/projects/aiquota/README.md")
s = p.read_text()
start = s.index("## Supported platforms")
end = s.index("### Important caveats")
p.write_text(s[:start] + section + s[end:])
print(f"table regenerated: {len(browser)} sign-in, {len(cred)} credential, "
      f"{len(manual)} manual")
