"""A local HTTP API, so other tools can build on aiquota instead of cloning it.

CodexBar has `codexbar serve`; openusage listens on :6736. Both exist for the
same reason: once the hard part (reading N providers honestly) is solved,
other people want that data in their own status bar, tmux prompt, Raycast
extension or shell script. Making them re-implement provider auth is waste.

Deliberately boring and safe:
  * binds 127.0.0.1 only — never a network interface
  * read-only; there is no endpoint that adds, removes or edits an account
  * never serves credentials, only readings
  * honours the same TTL cache as everything else, so a chatty client cannot
    make aiquota hammer a provider

Endpoints
    GET /                 human-readable index of what's available
    GET /healthz          {"ok": true, "version": "..."}
    GET /usage            every configured service
    GET /usage/<name>     one service
    GET /providers        the catalog: what could be added, and how
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from . import __version__

DEFAULT_PORT = 6737          # openusage squats 6736; don't collide


def _payload(only=None, force=False, ttl=300) -> Dict[str, Any]:
    from .core import attach_logos, collect
    data = collect(only=only, force=force, ttl=ttl)
    try:
        attach_logos(data)
    except Exception:
        pass
    return data


class _Handler(BaseHTTPRequestHandler):
    server_version = f"aiquota/{__version__}"
    quiet = True

    def log_message(self, format, *args):      # noqa: A002 - stdlib signature
        if not self.quiet:
            super().log_message(fmt, *args)

    def _send(self, code: int, body: bytes, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        # A local dashboard in a browser is a normal client for this.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        try:
            self.wfile.write(body)
        except BrokenPipeError:
            pass

    def _json(self, code: int, obj: Any):
        self._send(code, json.dumps(obj, indent=2).encode())

    def do_GET(self):                          # noqa: N802 - stdlib hook
        path = urlparse(self.path).path.rstrip("/") or "/"

        if path == "/healthz":
            return self._json(200, {"ok": True, "version": __version__})

        if path == "/":
            return self._send(200, INDEX.encode(), "text/html; charset=utf-8")

        if path == "/providers":
            from .catalog import CATALOG
            from .login_policy import policy_for
            out = []
            for c in CATALOG:
                mode, reason, url = policy_for(c["key"])
                out.append({"key": c["key"], "name": c["name"],
                            "support": c["support"], "how": mode,
                            "why": reason, "source": url})
            return self._json(200, {"providers": out})

        if path == "/usage":
            try:
                return self._json(200, _payload())
            except Exception as e:
                return self._json(500, {"error": f"{type(e).__name__}: {e}"})

        if path.startswith("/usage/"):
            name = path[len("/usage/"):]
            try:
                data = _payload(only=[name])
            except Exception as e:
                return self._json(500, {"error": f"{type(e).__name__}: {e}"})
            for s in data.get("services", []):
                if s.get("name") == name:
                    return self._json(200, s)
            return self._json(404, {"error": f"no service '{name}' configured"})

        return self._json(404, {"error": "not found", "try": "/"})


INDEX = """<!doctype html><meta charset=utf-8>
<title>aiquota</title>
<style>
 body{font:14px/1.6 -apple-system,BlinkMacSystemFont,sans-serif;
      max-width:38rem;margin:3rem auto;padding:0 1.5rem;color:#111}
 code{background:#f4f4f5;padding:.15em .4em;border-radius:4px;font-size:.9em}
 a{color:#0066cc} .m{color:#666;font-size:.9em}
 table{border-collapse:collapse;width:100%;margin:1rem 0}
 td{padding:.4rem .6rem;border-bottom:1px solid #eee;vertical-align:top}
</style>
<h1>aiquota</h1>
<p class=m>Read-only. Bound to localhost. Never serves credentials.</p>
<table>
<tr><td><a href="/usage"><code>/usage</code></a></td>
    <td>every configured service</td></tr>
<tr><td><code>/usage/&lt;name&gt;</code></td><td>one service</td></tr>
<tr><td><a href="/providers"><code>/providers</code></a></td>
    <td>what can be added, and how</td></tr>
<tr><td><a href="/healthz"><code>/healthz</code></a></td><td>liveness</td></tr>
</table>
<p class=m>Readings honour the same cache as the CLI, so polling this cannot
make aiquota hammer a provider.</p>
"""


class Server:
    """Wraps ThreadingHTTPServer so tests can start and stop it cleanly."""

    def __init__(self, port: int = DEFAULT_PORT, host: str = "127.0.0.1",
                 quiet: bool = True):
        handler = type("H", (_Handler,), {"quiet": quiet})
        self.httpd = ThreadingHTTPServer((host, port), handler)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        self.host = host
        self._t: Optional[threading.Thread] = None

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def start_background(self) -> "Server":
        self._t = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self._t.start()
        return self

    def serve_forever(self):
        self.httpd.serve_forever()

    def stop(self):
        try:
            self.httpd.shutdown()
        except Exception:
            pass
        try:
            self.httpd.server_close()
        except Exception:
            pass
