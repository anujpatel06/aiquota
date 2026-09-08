"""Native-feeling HTML picker rendered in a WKWebView-backed window.

`choose from list` can only show plain text — no logos, no layout. This
renders the catalog as a real macOS-styled list (logo, name, status pill) and
returns the chosen key on stdout.

Implementation: write a self-contained HTML file, open it in a chromeless
browser window, and have the page hand its choice back by navigating to a
loopback URL a tiny local server is listening on. Stdlib only.
"""
from __future__ import annotations

import http.server
import json
import os
import socket
import subprocess
import threading
import urllib.parse
from typing import Any, Dict, List, Optional

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "assets", "logos.json")


def _logos() -> Dict[str, str]:
    try:
        with open(ASSETS) as f:
            return json.load(f)
    except Exception:
        return {}


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>Add an AI account</title>
<style>
  :root {{
    --fg: rgba(255,255,255,0.92); --fg2: rgba(255,255,255,0.5);
    --bg: #1e1e1e; --row: rgba(255,255,255,0.04);
    --line: rgba(255,255,255,0.09); --sel: #0A84FF;
  }}
  @media (prefers-color-scheme: light) {{
    :root {{
      --fg: rgba(0,0,0,0.88); --fg2: rgba(0,0,0,0.5);
      --bg: #ececec; --row: rgba(0,0,0,0.03);
      --line: rgba(0,0,0,0.08); --sel: #007AFF;
    }}
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ height: 100%; }}
  body {{
    margin: 0; background: var(--bg); color: var(--fg);
    font: 13px/1.35 -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif;
    -webkit-font-smoothing: antialiased; letter-spacing: -0.01em;
    display: flex; flex-direction: column;
    user-select: none; -webkit-user-select: none;
  }}
  header {{ padding: 16px 18px 10px; }}
  h1 {{ margin: 0 0 2px; font-size: 15px; font-weight: 600;
       letter-spacing: -0.02em; }}
  .sub {{ font-size: 11.5px; color: var(--fg2); }}
  .scroll {{ flex: 1; overflow-y: auto; padding: 4px 10px 10px; }}
  .row {{
    display: flex; align-items: center; gap: 11px;
    padding: 8px 10px; border-radius: 9px; cursor: default;
  }}
  .row:hover {{ background: var(--row); }}
  .row.sel {{ background: var(--sel); }}
  .row.sel .name, .row.sel .desc, .row.sel .pill {{ color: #fff; }}
  .row.sel .pill {{ background: rgba(255,255,255,0.22); }}
  .ico {{
    width: 26px; height: 26px; border-radius: 7px; flex: none;
    background: rgba(127,127,127,0.14); object-fit: contain; padding: 3px;
  }}
  .ico.ph {{
    display: flex; align-items: center; justify-content: center;
    font-size: 12px; font-weight: 700; color: var(--fg2);
  }}
  .txt {{ flex: 1; min-width: 0; }}
  .name {{ font-weight: 560; font-size: 13px; }}
  .desc {{
    font-size: 11px; color: var(--fg2); margin-top: 1px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }}
  .pill {{
    font-size: 10px; font-weight: 600; padding: 2.5px 7px;
    border-radius: 20px; flex: none; letter-spacing: 0.01em;
  }}
  .live {{ background: rgba(48,209,88,0.16); color: #30D158; }}
  .soon {{ background: rgba(255,159,10,0.16); color: #FF9F0A; }}
  .man  {{ background: rgba(142,142,147,0.18); color: #8E8E93; }}
  .added {{ background: rgba(10,132,255,0.16); color: #0A84FF; }}
  footer {{
    display: flex; gap: 8px; justify-content: flex-end;
    padding: 11px 16px; border-top: 1px solid var(--line);
  }}
  button {{
    font: inherit; font-size: 13px; font-weight: 500; letter-spacing: -0.01em;
    padding: 5px 15px; border-radius: 7px; border: none; cursor: default;
    background: rgba(127,127,127,0.22); color: var(--fg);
  }}
  button.p {{ background: var(--sel); color: #fff; }}
  button:active {{ transform: scale(0.98); }}
</style></head><body>
<header>
  <h1>Add an AI account</h1>
  <div class="sub">Nothing is read until you choose it.</div>
</header>
<div class="scroll" id="list"></div>
<footer>
  <button onclick="pick('')">Cancel</button>
  <button class="p" onclick="confirmSel()">Add</button>
</footer>
<script>
const ITEMS = {items};
const PILL = {{live:['live','live usage'], soon:['soon','manual for now'],
               manual:['man','manual entry']}};
let sel = 0;

function pick(key) {{
  location.href = 'http://127.0.0.1:{port}/choose?key=' + encodeURIComponent(key);
}}
function confirmSel() {{ pick(ITEMS[sel] ? ITEMS[sel].key : ''); }}

const list = document.getElementById('list');
ITEMS.forEach((it, i) => {{
  const d = document.createElement('div');
  d.className = 'row' + (i === sel ? ' sel' : '');
  const [cls, label] = PILL[it.support] || PILL.manual;
  const ico = it.logo
    ? `<img class="ico" src="${{it.logo}}">`
    : `<div class="ico ph">${{(it.name[0]||'?').toUpperCase()}}</div>`;
  d.innerHTML = ico +
    `<div class="txt"><div class="name">${{it.name}}</div>` +
    `<div class="desc">${{it.note}}</div></div>` +
    (it.added ? `<span class="pill added">added</span>`
              : `<span class="pill ${{cls}}">${{label}}</span>`);
  d.onclick = () => {{ sel = i; draw(); }};
  d.ondblclick = () => pick(it.key);
  list.appendChild(d);
}});

function draw() {{
  [...list.children].forEach((c, i) => c.classList.toggle('sel', i === sel));
  const el = list.children[sel];
  if (el) el.scrollIntoView({{block: 'nearest'}});
}}
document.addEventListener('keydown', e => {{
  if (e.key === 'ArrowDown') {{ sel = Math.min(sel + 1, ITEMS.length - 1); draw(); e.preventDefault(); }}
  if (e.key === 'ArrowUp')   {{ sel = Math.max(sel - 1, 0); draw(); e.preventDefault(); }}
  if (e.key === 'Enter')     {{ confirmSel(); }}
  if (e.key === 'Escape')    {{ pick(''); }}
}});
</script></body></html>
"""


class _H(http.server.BaseHTTPRequestHandler):
    choice: Optional[str] = None
    done = threading.Event()

    def do_GET(self):  # noqa: N802
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        _H.choice = (q.get("key") or [""])[0]
        body = (b"<!doctype html><meta charset=utf-8>"
                b"<style>body{background:#1e1e1e}</style>"
                b"<script>window.close()</script>")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        _H.done.set()

    def log_message(self, *a):
        pass


def choose_gui(entries: List[Dict[str, Any]], tracked=set(),
               timeout: int = 300) -> Optional[str]:
    """Show the HTML picker. Returns the chosen catalog key, or None."""
    logos = _logos()
    items = [{
        "key": e["key"],
        "name": e["name"],
        "note": e.get("note", ""),
        "support": e.get("support", "manual"),
        "added": e["key"] in tracked,
        "logo": logos.get(e["key"], ""),
    } for e in entries]
    items.append({"key": "__other__", "name": "Something else…",
                  "note": "any AI service not listed above",
                  "support": "manual", "added": False, "logo": ""})

    port = _free_port()
    html = PAGE.format(items=json.dumps(items), port=port)

    import tempfile
    fd, path = tempfile.mkstemp(suffix=".html", prefix="aiquota_pick_")
    with os.fdopen(fd, "w") as f:
        f.write(html)

    _H.choice = None
    _H.done = threading.Event()
    srv = http.server.HTTPServer(("127.0.0.1", port), _H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    # A chromeless Chrome/Edge app window looks closest to a native sheet;
    # fall back to the default browser when neither is installed.
    size = "--window-size=460,600"
    for browser in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"):
        if os.path.exists(browser):
            subprocess.Popen(
                [browser, f"--app=file://{path}", size,
                 "--user-data-dir=" + tempfile.mkdtemp(prefix="aiq_prof_")],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            break
    else:
        subprocess.Popen(["open", "-W", path],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    _H.done.wait(timeout=timeout)
    srv.shutdown()
    try:
        os.unlink(path)
    except OSError:
        pass

    key = _H.choice
    return key or None
