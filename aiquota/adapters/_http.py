"""Shared HTTP helpers (stdlib urllib, no requests dependency)."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple

UA = "aiquota/0.1 (+https://github.com/anujpatel/aiquota)"


def request(url: str, headers: Optional[Dict[str, str]] = None,
            data: Optional[bytes] = None,
            timeout: int = 30) -> Tuple[int, Dict[str, str], bytes]:
    """Return (status, lowercased headers, body). Never raises on HTTP errors,
    because error responses often carry the headers we actually want.

    urllib is imported here rather than at module scope: it drags in the whole
    `email` package (~28ms), and the common path — a widget tick that hits the
    TTL cache — never makes a request at all.
    """
    import urllib.error
    import urllib.request

    h = {"User-Agent": UA, "Accept": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, {k.lower(): v for k, v in dict(r.headers).items()}, r.read()
    except urllib.error.HTTPError as e:
        body = b""
        try:
            body = e.read()
        except Exception:
            pass
        return e.code, {k.lower(): v for k, v in dict(e.headers or {}).items()}, body


def get_json(url: str, headers: Optional[Dict[str, str]] = None,
             timeout: int = 30, data: Optional[bytes] = None) -> Tuple[int, Any]:
    """GET, or POST when `data` is supplied (urllib infers the method)."""
    code, _, body = request(url, headers=headers, timeout=timeout, data=data)
    try:
        return code, json.loads(body.decode() or "null")
    except Exception:
        return code, None


def read_env_file(path: str, key: str) -> Optional[str]:
    """Pull KEY=value out of a .env-style file without importing dotenv."""
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line.startswith(key) and "=" in line:
                    v = line.partition("=")[2].strip().strip('"').strip("'")
                    return v or None
    except OSError:
        pass
    return None


def fmt_reset(epoch: Any) -> Optional[str]:
    import time
    try:
        return time.strftime("%a %H:%M", time.localtime(int(float(epoch))))
    except (TypeError, ValueError):
        return None
