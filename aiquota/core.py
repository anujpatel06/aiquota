"""Core types, config, cache, and the adapter registry.

Stdlib only — no third-party dependencies anywhere in this project.
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import os
import pkgutil
import sys
import time
from dataclasses import asdict, dataclass, field, fields
from typing import Any, Dict, List, Optional

APP_NAME = "aiquota"

# Confidence tiers. A dashboard that mixes real and guessed numbers without
# saying which is which is worse than no dashboard.
LIVE = "live"                  # fetched from the service, authoritative
LOCAL = "local"                # derived from local logs, an estimate
MANUAL = "manual"              # the user typed it in
UNCONFIGURED = "unconfigured"  # adapter exists but needs credentials
ERROR = "error"                # tried and failed


# --------------------------------------------------------------- paths

def config_dir() -> str:
    if os.environ.get("AIQUOTA_HOME"):
        return os.path.expanduser(os.environ["AIQUOTA_HOME"])
    xdg = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
        os.path.expanduser("~"), ".config")
    return os.path.join(xdg, APP_NAME)


def config_path() -> str:
    return os.path.join(config_dir(), "config.json")


def cache_path() -> str:
    return os.path.join(config_dir(), "cache.json")


def user_adapter_dir() -> str:
    return os.path.join(config_dir(), "adapters")


# --------------------------------------------------------------- types

@dataclass
class Window:
    """One rolling quota window (a 5-hour session, a weekly cap, a credit pool)."""
    label: str
    used_pct: float
    key: str = ""
    resets_at: Optional[str] = None
    status: Optional[str] = None


@dataclass
class Result:
    name: str
    service: str
    plan: str = ""
    tier: str = MANUAL
    windows: List[Window] = field(default_factory=list)
    note: str = ""
    error: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)
    # How much the number can be trusted, independent of whether it's live.
    # A live reading can still be percent-only (the provider reports 43% but
    # not 43-of-100), and a card should be able to say so rather than imply
    # a precision it doesn't have.
    #   exact        provider gave real counts
    #   percent_only provider gave a percentage with no underlying totals
    #   estimated    derived, not stated by the provider
    #   unknown      not established
    confidence: str = "unknown"
    # Structured failure reason (aiquota.failures.Failure.kind) when tier is
    # error — lets the UI show a fix-it hint instead of a raw status code.
    failure_kind: str = ""
    failure_hint: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["windows"] = [asdict(w) for w in self.windows]
        return d

    @staticmethod
    def from_dict(d: dict) -> "Result":
        d = dict(d)
        d["windows"] = [Window(**w) for w in d.get("windows", [])]
        # Tolerate caches written by older versions that lack these fields.
        for k, default in (("confidence", "unknown"), ("failure_kind", ""),
                           ("failure_hint", "")):
            d.setdefault(k, default)
        known = {f.name for f in fields(Result)}
        return Result(**{k: v for k, v in d.items() if k in known})


class Adapter:
    """Subclass this to teach aiquota about a new service.

    Contract: implement probe(conf) and return a Result. Never raise —
    catch your own errors and return tier=ERROR with a human message.
    """

    name: str = ""              # config key, e.g. "claude"
    service: str = ""           # display name, e.g. "Claude"
    summary: str = ""           # one line, shown by `aiquota adapters`
    setup: str = ""             # how to configure it, shown on unconfigured
    cost_note: str = ""         # set if probing consumes quota or money
    defaults: Dict[str, Any] = {}

    def probe(self, conf: Dict[str, Any]) -> Result:
        raise NotImplementedError

    def detect(self) -> List[Dict[str, Any]]:
        """Report credentials found on this machine WITHOUT using them.

        Powers `aiquota link`, which asks before anything is read. Return a
        list of {source, detail, config} — `config` being the settings that
        would enable it if the user consents. Must not perform network calls.
        """
        return []

    # convenience for subclasses
    def make(self, conf: Dict[str, Any], **kw) -> Result:
        kw.setdefault("plan", conf.get("plan") or self.service)
        return Result(name=self.name, service=self.service, **kw)


# ------------------------------------------------------------ registry

_REGISTRY: Dict[str, Adapter] = {}


def register(cls):
    """Class decorator: register an Adapter subclass."""
    inst = cls()
    if not inst.name:
        raise ValueError(f"{cls.__name__} must set .name")
    _REGISTRY[inst.name] = inst
    return cls


def registry() -> Dict[str, Adapter]:
    return _REGISTRY


def load_adapters(verbose: bool = False) -> Dict[str, Adapter]:
    """Import built-in adapters, then any user adapters dropped into
    ~/.config/aiquota/adapters/*.py — so people can add services without
    forking the project."""
    from . import adapters as pkg
    for m in pkgutil.iter_modules(pkg.__path__):
        if not m.name.startswith("_"):
            importlib.import_module(f"{pkg.__name__}.{m.name}")

    d = user_adapter_dir()
    if os.path.isdir(d):
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".py") or fn.startswith("_"):
                continue
            p = os.path.join(d, fn)
            try:
                spec = importlib.util.spec_from_file_location(
                    f"aiquota_user_{fn[:-3]}", p)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                if verbose:
                    print(f"[aiquota] loaded user adapter {fn}", file=sys.stderr)
            except Exception as e:
                print(f"[aiquota] user adapter {fn} failed to load: "
                      f"{type(e).__name__}: {e}", file=sys.stderr)
    return _REGISTRY


# -------------------------------------------------------------- config

def default_config() -> dict:
    return {
        "version": 1,
        "services": {
            "claude": {"adapter": "claude", "enabled": True, "plan": "Claude"},
            "chatgpt": {"adapter": "chatgpt", "enabled": True, "plan": "ChatGPT"},
        },
    }


def load_config() -> dict:
    p = config_path()
    if not os.path.exists(p):
        cfg = default_config()
        save_config(cfg)
        return cfg
    with open(p) as f:
        cfg = json.load(f)
    cfg.setdefault("version", 1)
    cfg.setdefault("services", {})
    return cfg


def save_config(cfg: dict) -> None:
    os.makedirs(config_dir(), exist_ok=True)
    p = config_path()
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, p)
    try:
        os.chmod(p, 0o600)   # may hold tokens
    except OSError:
        pass


def is_linked(conf: Dict[str, Any]) -> bool:
    """True only when a service actually has something to read.

    Merely appearing in config.json does NOT count — the default config ships
    entries for claude/chatgpt, and treating those as "added" told users an
    account was connected when nothing had been linked.

    Linked means one of:
      • a credential: api_key / token / token_files / autodiscover
      • a manual entry the user actually filled in
    """
    if not isinstance(conf, dict):
        return False
    for k in ("api_key", "token", "token_files", "auth_files", "session"):
        if conf.get(k):
            return True
    if conf.get("autodiscover"):
        return True
    if conf.get("adapter") == "manual":
        return any(conf.get(k) not in (None, "")
                   for k in ("credits", "credits_total", "used",
                             "limit", "renews_on"))
    return False


def stale_entries(cfg: Dict[str, Any]) -> Dict[str, str]:
    """Services stored as 'manual' that a real adapter now supports.

    A platform added before its adapter existed keeps the manual placeholder
    forever — silently showing "no values entered yet" while a live reader
    sits unused. Report them so the picker can offer to upgrade.
    """
    out = {}
    try:
        from .catalog import by_key
    except Exception:
        return out
    for key, entry in (cfg.get("services") or {}).items():
        if not isinstance(entry, dict) or entry.get("adapter") != "manual":
            continue
        cat = by_key(key)
        if cat and cat.get("adapter") and cat["adapter"] != "manual":
            out[key] = cat["adapter"]
    return out


def linked_services(cfg: Optional[dict] = None) -> set:
    """Keys of services that are genuinely linked."""
    cfg = cfg if cfg is not None else load_config()
    return {k for k, v in (cfg.get("services") or {}).items() if is_linked(v)}


# --------------------------------------------------------------- cache

def _read_cache() -> dict:
    try:
        with open(cache_path()) as f:
            return json.load(f)
    except Exception:
        return {}


def _write_cache(c: dict) -> None:
    os.makedirs(config_dir(), exist_ok=True)
    try:
        tmp = cache_path() + ".tmp"
        with open(tmp, "w") as f:
            json.dump(c, f)
        os.replace(tmp, cache_path())
    except OSError:
        pass


# ------------------------------------------------------------- collect

def attach_logos(data: dict) -> dict:
    """Embed each service's logo as a data URI, for UIs that render icons.

    Opt-in (`--logos`): the bundle is ~40KB of base64, which has no business
    riding along on every scripted `--json` call.
    """
    try:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "assets", "logos.json")
        with open(path) as f:
            logos = json.load(f)
    except Exception:
        return data
    for s in data.get("services", []):
        uri = logos.get(s.get("name", ""))
        if uri:
            s["logo"] = uri
    return data


def collect(only: Optional[List[str]] = None, force: bool = False,
            ttl: int = 300) -> dict:
    """Probe configured services, honouring a TTL cache.

    The cache matters: some adapters cost real quota to probe, so a widget on
    a short refresh timer must not hammer them.
    """
    load_adapters()
    cfg = load_config()
    cache = _read_cache()
    now = time.time()
    results, used_cache = [], False

    for key, sconf in cfg.get("services", {}).items():
        if only and key not in only:
            continue
        if not sconf.get("enabled", True):
            continue

        aname = sconf.get("adapter") or key
        ad = _REGISTRY.get(aname)
        if ad is None:
            results.append(Result(name=key, service=sconf.get("plan") or key,
                                  tier=ERROR,
                                  error=f"no adapter '{aname}' installed"))
            continue

        ent = cache.get(key)
        # Only LIVE results are worth caching: manual values change by hand
        # (caching them shows stale numbers) and errors should be retried.
        if (not force and ent and isinstance(ent, dict)
                and now - ent.get("at", 0) < ttl
                and (ent.get("result") or {}).get("tier") == LIVE):
            try:
                r = Result.from_dict(ent["result"])
                r.extra = dict(r.extra or {})
                r.extra["cached_age_s"] = int(now - ent["at"])
                results.append(r)
                used_cache = True
                continue
            except Exception:
                pass

        try:
            probe_conf = dict(sconf)
            probe_conf["_key"] = key          # adapters may use this as a label
            r = ad.probe(probe_conf)
        except Exception as e:                      # adapter bug guard
            r = Result(name=key, service=ad.service or key, tier=ERROR,
                       error=f"adapter raised {type(e).__name__}: {e}")
        r.name = key
        results.append(r)
        if r.tier == LIVE:
            cache[key] = {"at": now, "result": r.to_dict()}

    _write_cache(cache)
    return {
        "generated_at": now,
        "any_cached": used_cache,
        "services": [r.to_dict() for r in results],
        "config_path": config_path(),
    }
