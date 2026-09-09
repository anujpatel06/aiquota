"""Dialogs that look like the rest of aiquota, not like a 1990s alert.

`osascript ... display dialog` cannot be styled at all: no icon, no type
hierarchy, no colour, and it stamps "aiquota" across the top as if the app
were shouting its own name. Next to the widget and the platform picker it
looked like a different product.

These render the same HTML material the picker uses — logo, title, body,
macOS-style buttons — in the same chromeless browser window, and hand the
answer back over a loopback URL. Stdlib only.

`picker.confirm()` and `picker.ask()` fall back to AppleScript when this
cannot start, so a machine with no Chrome-family browser still works.
"""
from __future__ import annotations

import http.server
import json
import os
import socket
import subprocess
import threading
import urllib.parse
from typing import Dict, List, Optional

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "assets", "logos.json")


def _logo(key: str) -> str:
    try:
        with open(ASSETS) as f:
            return (json.load(f) or {}).get(key, "")
    except Exception:
        return ""


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>{title}</title>
<style>
  :root {{
    --fg: rgba(255,255,255,0.92); --fg2: rgba(255,255,255,0.55);
    --fg3: rgba(255,255,255,0.38);
    --bg: #1e1e1e; --line: rgba(255,255,255,0.10);
    --btn: rgba(255,255,255,0.13); --accent: #0A84FF; --danger: #FF453A;
    --code: rgba(255,255,255,0.06);
  }}
  @media (prefers-color-scheme: light) {{
    :root {{
      --fg: rgba(0,0,0,0.88); --fg2: rgba(0,0,0,0.58);
      --fg3: rgba(0,0,0,0.4);
      --bg: #f2f2f2; --line: rgba(0,0,0,0.09);
      --btn: rgba(0,0,0,0.08); --accent: #007AFF; --danger: #FF3B30;
      --code: rgba(0,0,0,0.05);
    }}
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ height: 100%; margin: 0; }}
  body {{
    background: var(--bg); color: var(--fg);
    font: 13px/1.45 -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif;
    -webkit-font-smoothing: antialiased; letter-spacing: -0.01em;
    display: flex; flex-direction: column;
    user-select: none; cursor: default; overflow: hidden;
  }}
  .body {{ flex: 1; padding: 26px 26px 8px; overflow-y: auto; }}
  .icon {{
    width: 42px; height: 42px; border-radius: 11px; margin-bottom: 14px;
    object-fit: contain; padding: 5px; background: var(--code);
  }}
  .glyph {{
    width: 42px; height: 42px; border-radius: 11px; margin-bottom: 14px;
    display: flex; align-items: center; justify-content: center;
    font-size: 20px; background: linear-gradient(135deg,#0A84FF,#5E5CE6);
  }}
  h1 {{
    margin: 0 0 8px; font-size: 16px; font-weight: 600;
    letter-spacing: -0.02em; line-height: 1.25;
  }}
  p {{ margin: 0 0 10px; color: var(--fg2); }}
  p.lead {{ color: var(--fg); }}
  .rows {{
    margin: 14px 0 4px; border-radius: 10px; background: var(--code);
    overflow: hidden;
  }}
  .row {{
    display: flex; gap: 10px; padding: 9px 12px;
    border-top: 0.5px solid var(--line); font-size: 12px;
  }}
  .row:first-child {{ border-top: none; }}
  .row .k {{ color: var(--fg3); flex: none; min-width: 74px; }}
  .row .v {{ color: var(--fg2); word-break: break-word; }}
  .row .v code {{
    font: 11.5px/1.4 ui-monospace, SFMono-Regular, Menlo, monospace;
    color: var(--fg);
  }}
  .note {{ font-size: 11.5px; color: var(--fg3); margin-top: 12px; }}
  input {{
    width: 100%; margin-top: 12px; padding: 8px 10px;
    font: inherit; color: var(--fg);
    background: var(--code); border: 0.5px solid var(--line);
    border-radius: 8px; outline: none;
  }}
  input:focus {{ border-color: var(--accent); }}
  .foot {{
    display: flex; justify-content: flex-end; gap: 10px;
    padding: 14px 26px 20px;
  }}
  button {{
    font: inherit; font-size: 13px; font-weight: 500;
    padding: 6px 16px; min-width: 84px;
    border: none; border-radius: 8px; cursor: pointer;
    background: var(--btn); color: var(--fg);
  }}
  button.primary {{ background: var(--accent); color: #fff; }}
  button.danger {{ background: var(--danger); color: #fff; }}
  button:active {{ opacity: 0.75; }}
</style></head><body>
  <div class="body">
    {icon}
    <h1>{title}</h1>
    {html}
  </div>
  <div class="foot">
    {cancel}
    <button class="primary {okclass}" id="ok">{ok}</button>
  </div>
<script>
  const send = (v) => {{
    const inp = document.getElementById("val");
    const q = "/answer?v=" + encodeURIComponent(v) +
      (inp ? "&t=" + encodeURIComponent(inp.value) : "");
    fetch(q).then(() => setTimeout(() => window.close(), 60));
  }};
  document.getElementById("ok").onclick = () => send("ok");
  const c = document.getElementById("cancel");
  if (c) c.onclick = () => send("cancel");
  document.addEventListener("keydown", (e) => {{
    if (e.key === "Enter") {{ e.preventDefault(); send("ok"); }}
    if (e.key === "Escape") {{ e.preventDefault(); send(c ? "cancel" : "ok"); }}
  }});
  const inp = document.getElementById("val");
  if (inp) inp.focus();
</script>
</body></html>"""


class _H(http.server.BaseHTTPRequestHandler):
    answer: Optional[str] = None
    text: str = ""
    done = threading.Event()
    page: bytes = b""

    def do_GET(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/answer":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(_H.page)))
            self.end_headers()
            self.wfile.write(_H.page)
            return
        q = urllib.parse.parse_qs(parsed.query)
        _H.answer = (q.get("v") or ["cancel"])[0]
        _H.text = (q.get("t") or [""])[0]
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self.end_headers()
        _H.done.set()

    def log_message(self, *a):
        pass


def _screen() -> tuple:
    try:
        out = subprocess.run(
            ["osascript", "-e",
             'tell application "Finder" to get bounds of window of desktop'],
            capture_output=True, text=True, timeout=4).stdout.strip()
        p = [int(x) for x in out.split(", ")]
        return p[2], p[3]
    except Exception:
        return 1440, 900


def show(title: str, html: str, ok: str = "OK", cancel: Optional[str] = None,
         logo_key: str = "", field: bool = False, danger: bool = False,
         width: int = 440, height: int = 300,
         timeout: int = 300) -> Optional[Dict[str, str]]:
    """Show a dialog. Returns {"ok": bool, "text": str} or None if unavailable.

    None means the window could not be opened at all — the caller should fall
    back to AppleScript rather than silently treating it as a cancel.
    """
    browser = None
    for b in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
              "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"):
        if os.path.exists(b):
            browser = b
            break
    if not browser:
        return None

    port = _free_port()
    _H.answer, _H.text = None, ""
    _H.done = threading.Event()
    srv = http.server.HTTPServer(("127.0.0.1", port), _H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    logo = _logo(logo_key) if logo_key else ""
    icon = (f'<img class="icon" src="{logo}">' if logo
            else '<div class="glyph">◐</div>')
    if field:
        html += '<input id="val" autocomplete="off" spellcheck="false">'
    cancel_html = (f'<button id="cancel">{cancel}</button>' if cancel else "")

    _H.page = PAGE.format(
        title=title, html=html, ok=ok, cancel=cancel_html, icon=icon,
        okclass="danger" if danger else "").encode()

    sw, sh = _screen()
    x, y = max(0, (sw - width) // 2), max(0, (sh - height) // 3)
    profile = os.path.join(os.path.expanduser("~"), ".cache", "aiquota",
                           "browser")
    os.makedirs(profile, exist_ok=True)

    subprocess.Popen(
        [browser, f"--app=http://127.0.0.1:{port}/",
         f"--window-size={width},{height}",
         f"--window-position={x},{y}",
         f"--user-data-dir={profile}",
         "--no-first-run", "--no-default-browser-check", "--disable-extensions",
         "--disable-background-networking", "--disable-sync",
         "--disable-features=Translate,MediaRouter", "--no-service-autorun"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _front():
        import time as _t
        for _ in range(12):
            _t.sleep(0.25)
            r = subprocess.run(
                ["osascript", "-e",
                 'tell application "System Events" to set frontmost of '
                 '(first process whose name contains "Chrome" or name '
                 'contains "Edge" or name contains "Brave") to true'],
                capture_output=True, text=True)
            if r.returncode == 0:
                return
    threading.Thread(target=_front, daemon=True).start()

    got = _H.done.wait(timeout=timeout)
    srv.shutdown()
    if not got:
        # Timed out with the window still open. Treat as "no answer" rather
        # than a cancel: the caller decides, and a destructive action must
        # never proceed on a dialog nobody answered.
        return {"ok": False, "text": "", "timeout": True}
    return {"ok": _H.answer == "ok", "text": _H.text, "timeout": False}


def rows(pairs: List[tuple]) -> str:
    """Render label/value pairs as the grouped rows macOS uses for detail."""
    if not pairs:
        return ""
    out = ['<div class="rows">']
    for k, v in pairs:
        out.append(f'<div class="row"><span class="k">{k}</span>'
                   f'<span class="v">{v}</span></div>')
    out.append("</div>")
    return "".join(out)
