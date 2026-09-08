"""Browser-based OAuth for adapters that support it.

The point: the user clicks "Add OpenRouter", their browser opens, they log in
on OpenRouter's own site, and the app receives a key. No pasting, and this
tool never sees their password.

Implements OAuth 2.0 PKCE with a loopback redirect (RFC 8252, the standard
approach for native apps).
"""
from __future__ import annotations

import base64
import hashlib
import http.server
import json
import os
import secrets
import socket
import threading
import urllib.parse
import urllib.request
import webbrowser
from typing import Optional, Tuple


def _pkce_pair() -> Tuple[str, str]:
    """Return (verifier, S256 challenge)."""
    verifier = base64.urlsafe_b64encode(os.urandom(64)).decode().rstrip("=")
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return verifier, challenge


def _free_port(preferred=(51423, 51424, 51425, 8899)) -> int:
    for p in preferred:
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


DONE_PAGE = """<!doctype html><meta charset="utf-8">
<title>aiquota</title>
<style>
 body{{margin:0;height:100vh;display:flex;align-items:center;
 justify-content:center;background:#0d1117;color:#e6edf3;
 font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}}
 .c{{text-align:center}} h1{{font-size:1.1rem;margin:0 0 .4rem}}
 p{{color:#8b949e;font-size:.85rem;margin:0}}
 .m{{font-size:2rem;margin-bottom:.6rem}}
</style>
<div class=c><div class=m>{icon}</div><h1>{title}</h1><p>{msg}</p></div>
"""


class _Handler(http.server.BaseHTTPRequestHandler):
    code = None
    error = None

    def do_GET(self):  # noqa: N802
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if "code" in q:
            _Handler.code = q["code"][0]
            body = DONE_PAGE.format(icon="✓", title="Connected",
                                    msg="You can close this tab and return to aiquota.")
        else:
            _Handler.error = q.get("error", ["no code returned"])[0]
            body = DONE_PAGE.format(icon="✕", title="Authorisation failed",
                                    msg=_Handler.error)
        data = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):  # silence the default stderr logging
        pass


def openrouter_login(timeout: int = 180) -> Tuple[Optional[str], Optional[str]]:
    """Run OpenRouter's OAuth PKCE flow. Returns (api_key, error).

    Verified against https://openrouter.ai/docs/use-cases/oauth-pkce —
    no client registration, loopback redirects explicitly supported.
    """
    verifier, challenge = _pkce_pair()
    port = _free_port()
    redirect = f"http://localhost:{port}/callback"

    _Handler.code = None
    _Handler.error = None
    try:
        srv = http.server.HTTPServer(("127.0.0.1", port), _Handler)
    except OSError as e:
        return None, f"could not open a local port: {e}"

    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()

    url = ("https://openrouter.ai/auth?"
           + urllib.parse.urlencode({
               "callback_url": redirect,
               "code_challenge": challenge,
               "code_challenge_method": "S256",
           }))
    webbrowser.open(url)

    # Wait for the browser to come back.
    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _Handler.code or _Handler.error:
            break
        time.sleep(0.25)
    srv.shutdown()

    if _Handler.error:
        return None, _Handler.error
    if not _Handler.code:
        return None, "timed out waiting for the browser"

    # Exchange the code for a user-controlled API key.
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/auth/keys",
        data=json.dumps({"code": _Handler.code,
                         "code_verifier": verifier,
                         "code_challenge_method": "S256"}).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            payload = json.loads(r.read().decode())
    except Exception as e:
        return None, f"code exchange failed: {type(e).__name__}: {e}"

    key = payload.get("key")
    if not key:
        return None, "no key in response"
    return key, None
