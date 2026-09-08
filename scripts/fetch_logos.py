#!/usr/bin/env python3
"""Fetch each platform's favicon into aiquota/assets/logos/ as base64 data URIs.

Bundled at build time so the picker renders instantly and works offline —
no network calls, no third-party tracking when the dialog opens.
"""
import base64
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aiquota.catalog import CATALOG  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "aiquota", "assets", "logos.json")

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.headers.get("Content-Type", "")


def main():
    logos = {}
    for e in CATALOG:
        dom = e.get("domain")
        if not dom:
            continue
        got = False
        for url in (
            f"https://www.google.com/s2/favicons?sz=128&domain={dom}",
            f"https://icons.duckduckgo.com/ip3/{dom}.ico",
            f"https://{dom}/favicon.ico",
        ):
            try:
                data, ctype = fetch(url)
                if len(data) < 100:      # placeholder/globe fallback
                    continue
                mime = "image/png" if "png" in ctype.lower() else (
                    "image/x-icon" if "icon" in ctype.lower() or url.endswith(".ico")
                    else "image/png")
                logos[e["key"]] = (f"data:{mime};base64,"
                                   + base64.b64encode(data).decode())
                print(f"  {e['name']:<18} {len(data):>6}B  {url.split('/')[2]}")
                got = True
                break
            except Exception:
                continue
        if not got:
            print(f"  {e['name']:<18} FAILED")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(logos, f)
    size = os.path.getsize(OUT) / 1024
    print(f"\nwrote {OUT}  ({len(logos)} logos, {size:.0f} KB)")


if __name__ == "__main__":
    main()
