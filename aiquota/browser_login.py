"""Browser sign-in: let the user log in with whatever account they like.

Why this exists
---------------
Pasting an API key is the wrong ask for a subscription tracker. API keys are
tied to *developer billing*, not to the Pro/Max/Plus subscription whose quota
the user actually wants to see — and asking someone to paste a secret into a
third-party tool is a bad habit to teach.

Instead: we open a normal browser window pointed at the provider's own login
page. The user signs in there, with any email they choose, exactly as they
would in their own browser. aiquota never sees the password, and never asks
for one. When the session exists, we read it back out of *our* window.

How the session is read
-----------------------
Chrome encrypts its cookie store (macOS Keychain + AES), which stdlib cannot
decrypt, and reaching into another app's cookie jar would be exactly the kind
of silent credential-borrowing this project already decided against. So the
window we launch is ours, isolated in its own profile directory, and we ask
Chrome for the cookies over the DevTools protocol.

CDP needs a websocket. The stdlib has no websocket client, so `_WS` below
implements the minimum of RFC 6455 needed for a handful of request/response
round trips: a client handshake, masked text frames out, unmasked frames in.
That is a deliberate trade — a raw socket beats adding a dependency to a tool
whose whole promise is that `pip install aiquota` never breaks.

Scope of what is captured
-------------------------
Only cookies for the domain being logged into, and only from the profile this
module created. The profile is deleted when the flow ends.
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import tempfile
import time
import urllib.request
from typing import Dict, List, Optional

CHROME_PATHS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]


class LoginError(RuntimeError):
    """Raised when the browser flow cannot be completed."""


def find_browser() -> Optional[str]:
    for p in CHROME_PATHS:
        if os.path.exists(p):
            return p
    return None


# --------------------------------------------------------------- websocket

class _WS:
    """Just enough RFC 6455 to drive CDP. Not a general websocket client."""

    def __init__(self, url: str):
        if not url.startswith("ws://"):
            raise LoginError("unexpected debugger url: %s" % url[:40])
        hostport, _, path = url[5:].partition("/")
        host, _, port = hostport.partition(":")
        self.sock = socket.create_connection((host, int(port)), timeout=15)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((
            "GET /%s HTTP/1.1\r\nHost: %s\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            "Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n"
            % (path, hostport, key)
        ).encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise LoginError("browser closed the debugger connection")
            buf += chunk
        if b" 101 " not in buf.split(b"\r\n")[0]:
            raise LoginError("debugger handshake refused")

    def send(self, obj: dict) -> None:
        data = json.dumps(obj).encode()
        mask = os.urandom(4)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        n = len(data)
        if n < 126:
            hdr = struct.pack("!BB", 0x81, 0x80 | n)
        elif n < 65536:
            hdr = struct.pack("!BBH", 0x81, 0x80 | 126, n)
        else:
            hdr = struct.pack("!BBQ", 0x81, 0x80 | 127, n)
        self.sock.sendall(hdr + mask + masked)

    def _read(self, n: int) -> bytes:
        out = b""
        while len(out) < n:
            chunk = self.sock.recv(n - len(out))
            if not chunk:
                raise LoginError("debugger connection closed")
            out += chunk
        return out

    def recv(self) -> dict:
        _b0, b1 = self._read(2)
        ln = b1 & 0x7F
        if ln == 126:
            ln = struct.unpack("!H", self._read(2))[0]
        elif ln == 127:
            ln = struct.unpack("!Q", self._read(8))[0]
        if b1 & 0x80:
            mask = self._read(4)
            body = bytes(c ^ mask[i % 4] for i, c in enumerate(self._read(ln)))
        else:
            body = self._read(ln)
        try:
            return json.loads(body)
        except ValueError:
            return {}

    def call(self, method: str, msg_id: int, **params) -> dict:
        self.send({"id": msg_id, "method": method, "params": params})
        deadline = time.time() + 20
        while time.time() < deadline:
            msg = self.recv()
            if msg.get("id") == msg_id:
                return msg.get("result", {})
        raise LoginError("no reply to %s" % method)

    def close(self) -> None:
        try:
            self.sock.close()
        except Exception:
            pass


# ------------------------------------------------------------------- flow

class LoginWindow:
    """A throwaway browser window we own, driven over CDP."""

    def __init__(self, url: str, width: int = 520, height: int = 700):
        self.browser = find_browser()
        if not self.browser:
            raise LoginError(
                "No Chrome-family browser found. Install Google Chrome, or "
                "link this service another way.")
        self.profile = tempfile.mkdtemp(prefix="aiquota_login_")
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        self.proc = subprocess.Popen([
            self.browser,
            "--user-data-dir=%s" % self.profile,
            "--remote-debugging-port=%d" % self.port,
            "--no-first-run", "--no-default-browser-check",
            "--no-service-autorun", "--disable-extensions",
            "--window-size=%d,%d" % (width, height),
            "--app=%s" % url,
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.ws: Optional[_WS] = None
        self._id = 0

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def attach(self, timeout: float = 25.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                tabs = json.load(urllib.request.urlopen(
                    "http://127.0.0.1:%d/json/list" % self.port, timeout=1))
                for t in tabs:
                    if t.get("webSocketDebuggerUrl") and t.get("type") == "page":
                        self.ws = _WS(t["webSocketDebuggerUrl"])
                        return
            except Exception:
                pass
            time.sleep(0.2)
        raise LoginError("browser did not open in time")

    def current_url(self) -> str:
        if not self.ws:
            return ""
        try:
            r = self.ws.call("Runtime.evaluate", self._next_id(),
                             expression="location.href", returnByValue=True)
            return r.get("result", {}).get("value", "") or ""
        except Exception:
            return ""

    def cookies_for(self, domains: List[str]) -> Dict[str, str]:
        """Cookies whose domain matches one of `domains`."""
        if not self.ws:
            return {}
        res = self.ws.call("Network.getAllCookies", self._next_id())
        out = {}
        for c in res.get("cookies", []):
            dom = (c.get("domain") or "").lstrip(".")
            if any(dom == d or dom.endswith("." + d) for d in domains):
                out[c["name"]] = c["value"]
        return out

    def fetch_json(self, url: str, timeout: float = 20.0):
        """GET `url` from inside the page and return (status, parsed-json).

        Some providers cannot be read by a stdlib HTTP client at all:
        Cloudflare fingerprints the TLS handshake (Perplexity answers a
        challenge page), and Midjourney's host rejects Python's TLS outright.
        A fetch() running in the page uses Chrome's own TLS stack, headers
        and session, so it reaches the app where urllib cannot.

        Returns (0, None) if the page could not run the request.
        """
        if not self.ws:
            return 0, None
        expr = (
            "(async () => { try {"
            f"  const r = await fetch({json.dumps(url)}, "
            "    {credentials:'include', headers:{'Accept':'application/json'}});"
            "  const t = await r.text();"
            "  return JSON.stringify({s:r.status, b:t.slice(0, 200000)});"
            "} catch (e) { return JSON.stringify({s:0, b:String(e)}); } })()"
        )
        try:
            res = self.ws.call("Runtime.evaluate", self._next_id(),
                               expression=expr, awaitPromise=True,
                               returnByValue=True)
        except LoginError:
            return 0, None
        raw = res.get("result", {}).get("value")
        if not raw:
            return 0, None
        try:
            outer = json.loads(raw)
            body = outer.get("b") or ""
            return int(outer.get("s") or 0), json.loads(body)
        except (ValueError, TypeError):
            return int(outer.get("s") or 0) if isinstance(outer, dict) else 0, None

    def alive(self) -> bool:
        return self.proc.poll() is None

    def close(self) -> None:
        if self.ws:
            self.ws.close()
        try:
            self.proc.terminate()
            self.proc.wait(timeout=5)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass
        shutil.rmtree(self.profile, ignore_errors=True)


def login_and_read(url: str, domains: List[str], want: List[str],
                   endpoints: List[str], timeout: int = 300,
                   settle: float = 1.5) -> Dict[str, Any]:
    """Sign in, then read `endpoints` from inside that same page.

    For providers a stdlib HTTP client cannot reach at all — Cloudflare TLS
    fingerprinting, or a host that refuses Python's TLS. Cookies are still
    captured so a later refresh can try them directly, but the readings taken
    here are what the widget shows first.

    Returns {"session": {...}, "data": {endpoint: json}} or {} if the user
    never finished signing in.
    """
    win = LoginWindow(url)
    try:
        win.attach()
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not win.alive():
                return {}
            jar = win.cookies_for(domains)
            if all(k in jar for k in want):
                time.sleep(settle)
                if win.alive():
                    later = win.cookies_for(domains)
                    if all(k in later for k in want):
                        jar = later
                data = {}
                for ep in endpoints:
                    status, body = win.fetch_json(ep)
                    if status == 200 and body is not None:
                        data[ep] = body
                return {"session": {k: jar[k] for k in want}, "data": data}
            time.sleep(1.0)
        return {}
    finally:
        win.close()


def refresh_via_browser(url: str, endpoints: List[str],
                        timeout: int = 60) -> Dict[str, Any]:
    """Re-read `endpoints` in a headless-ish window using the stored profile.

    Used on refresh for providers that cannot be read any other way. Opens
    the page, waits briefly for the session to restore, and reads.
    """
    win = LoginWindow(url, width=420, height=420)
    try:
        win.attach()
        time.sleep(3.0)
        out = {}
        for ep in endpoints:
            status, body = win.fetch_json(ep)
            if status == 200 and body is not None:
                out[ep] = body
        return out
    finally:
        win.close()


def login_and_capture(url: str, domains: List[str], want: List[str],
                      timeout: int = 300,
                      settle: float = 1.5,
                      on_wait=None) -> Dict[str, str]:
    """Open `url`, wait for the user to sign in, return the wanted cookies.

    Blocks until every name in `want` is present, the user closes the window,
    or `timeout` elapses. Returns {} if the user gave up — never partial junk.

    A session cookie can appear part-way through a multi-step login (SSO
    bounce, MFA), so once the cookies show up we wait `settle` seconds and
    re-read them, taking the later values. Closing the window the moment a
    name first appears can capture a half-finished session.
    """
    win = LoginWindow(url)
    try:
        win.attach()
        deadline = time.time() + timeout
        notified = False
        while time.time() < deadline:
            if not win.alive():
                return {}
            jar = win.cookies_for(domains)
            if all(k in jar for k in want):
                time.sleep(settle)
                if win.alive():
                    later = win.cookies_for(domains)
                    if all(k in later for k in want):
                        jar = later
                return {k: jar[k] for k in want}
            if on_wait and not notified:
                on_wait()
                notified = True
            time.sleep(1.0)
        return {}
    finally:
        win.close()
