"""aiquota CLI — see all your AI subscription quotas in one place."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

from .core import (ERROR, LIVE, LOCAL, MANUAL, UNCONFIGURED, attach_logos,
                   collect,
                   config_path, load_adapters, load_config, registry,
                   save_config, user_adapter_dir)

# ------------------------------------------------------------- colour

def _use_colour(flag: str) -> bool:
    if flag == "always":
        return True
    if flag == "never" or os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()


class C:
    on = False
    @classmethod
    def _w(cls, code, s):
        return f"\033[{code}m{s}\033[0m" if cls.on else s
    @classmethod
    def dim(cls, s): return cls._w("2", s)
    @classmethod
    def bold(cls, s): return cls._w("1", s)
    @classmethod
    def green(cls, s): return cls._w("32", s)
    @classmethod
    def yellow(cls, s): return cls._w("33", s)
    @classmethod
    def red(cls, s): return cls._w("31", s)
    @classmethod
    def cyan(cls, s): return cls._w("36", s)


TIER_LABEL = {LIVE: ("live", C.green), LOCAL: ("estimate", C.yellow),
              MANUAL: ("manual", C.dim), UNCONFIGURED: ("setup", C.yellow),
              ERROR: ("error", C.red)}


def _bar(pct: float, width: int = 24) -> str:
    pct = max(0.0, min(100.0, float(pct)))
    fill = int(round(pct / 100 * width))
    bar = "█" * fill + "░" * (width - fill)
    colour = C.red if pct >= 85 else (C.yellow if pct >= 60 else C.green)
    return colour(bar)


def _coerce(v: str) -> Any:
    low = v.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("null", "none", ""):
        return None
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        return v


def _kv(pairs: Optional[List[str]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for p in pairs or []:
        k, sep, v = p.partition("=")
        if not sep:
            print(f"warning: ignoring '{p}' (expected key=value)", file=sys.stderr)
            continue
        out[k.strip()] = _coerce(v.strip())
    return out


# ------------------------------------------------------------ render

def render_text(d: dict, verbose: bool = False) -> str:
    lines: List[str] = []
    svcs = d["services"]
    if not svcs:
        return ("No services configured.\n"
                "  aiquota adapters      list what's available\n"
                "  aiquota add claude    start tracking one\n")

    for s in svcs:
        label, colour = TIER_LABEL.get(s["tier"], ("?", C.dim))
        head = f"{C.bold(s['service'])}"
        if s.get("plan") and s["plan"] != s["service"]:
            head += C.dim(f"  {s['plan']}")
        age = (s.get("extra") or {}).get("cached_age_s")
        suffix = colour(f"[{label}]")
        if age:
            suffix += C.dim(f" cached {age}s")
        lines.append(f"{head}  {suffix}")

        for w in s.get("windows", []):
            pct = float(w["used_pct"])
            reset = C.dim(f"  resets {w['resets_at']}") if w.get("resets_at") else ""
            lines.append(f"  {w['label']:<18} {_bar(pct)} {pct:5.1f}%{reset}")

        ex = s.get("extra") or {}
        bits = []
        if ex.get("credits") is not None:
            bits.append(f"credits: {ex['credits']}")
        if ex.get("renews_in_days") is not None:
            bits.append(f"renews in {ex['renews_in_days']}d")
        if ex.get("binding"):
            bits.append(f"binding: {ex['binding']}")
        if ex.get("overage"):
            bits.append(f"overage: {ex['overage']}")
        if bits:
            lines.append(C.dim("  " + " · ".join(bits)))

        if s.get("error"):
            lines.append("  " + C.red(s["error"]))
        if s.get("note") and (verbose or not s.get("windows")):
            lines.append(C.dim(f"  {s['note']}"))
        if verbose and ex.get("source"):
            lines.append(C.dim(f"  source: {ex['source']}"))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_compact(d: dict) -> str:
    """One line, for a status bar / tmux / shell prompt."""
    parts = []
    for s in d["services"]:
        if not s.get("windows"):
            continue
        w = max(s["windows"], key=lambda x: float(x["used_pct"]))
        parts.append(f"{s['service'][:2].upper()} {float(w['used_pct']):.0f}%")
    return " | ".join(parts) if parts else "no live quota data"


# --------------------------------------------------------------- cmds

def cmd_status(a) -> int:
    d = collect(only=a.service or None, force=a.refresh, ttl=a.ttl)
    if getattr(a, "logos", False):
        d = attach_logos(d)
    if a.json:
        json.dump(d, sys.stdout, indent=2)
        print()
    elif a.compact:
        print(render_compact(d))
    else:
        sys.stdout.write(render_text(d, verbose=a.verbose))
    if a.html:
        from .render import write_html
        write_html(d, a.html)
        print(f"wrote {a.html}", file=sys.stderr)
    worst = 0.0
    for s in d["services"]:
        for w in s.get("windows", []):
            worst = max(worst, float(w["used_pct"]))
    if a.exit_code and worst >= a.threshold:
        return 2
    return 0


def cmd_adapters(a) -> int:
    load_adapters(verbose=a.verbose)
    reg = registry()
    if a.json:
        json.dump({k: {"service": v.service, "summary": v.summary,
                       "setup": v.setup, "cost_note": v.cost_note}
                   for k, v in sorted(reg.items())}, sys.stdout, indent=2)
        print()
        return 0
    print(C.bold("Available adapters:\n"))
    for k, ad in sorted(reg.items()):
        print(f"  {C.cyan(k):<20} {ad.summary}")
        if ad.cost_note:
            print(C.dim(f"  {'':<18} ⚠ {ad.cost_note}"))
    print(C.dim(f"\nDrop custom adapters in {user_adapter_dir()}/"))
    print(C.dim("Track anything without code:  aiquota add <name> --adapter manual"))
    return 0


def cmd_add(a) -> int:
    load_adapters()
    cfg = load_config()
    name = a.name
    adapter = a.adapter or name
    if adapter not in registry():
        print(f"error: no adapter '{adapter}'. Try: aiquota adapters",
              file=sys.stderr)
        return 1
    if name in cfg["services"] and not a.force:
        print(f"error: '{name}' already exists (use --force to overwrite)",
              file=sys.stderr)
        return 1

    entry: Dict[str, Any] = {"adapter": adapter, "enabled": True}
    if a.plan:
        entry["plan"] = a.plan
    if adapter == "manual":
        # brand name comes from the config key; --plan is the tier label
        entry.setdefault("service", name.replace("-", " ").replace("_", " ").title())
    entry.update(_kv(a.set))
    cfg["services"][name] = entry
    save_config(cfg)
    print(f"added '{name}' (adapter: {adapter})")
    ad = registry()[adapter]
    if ad.setup:
        print(C.dim(f"  setup: {ad.setup}"))
    return 0


def cmd_remove(a) -> int:
    cfg = load_config()
    missing = [n for n in a.name if n not in cfg["services"]]
    if missing:
        print(f"error: not tracked: {', '.join(missing)}", file=sys.stderr)
        return 1
    if not a.yes:
        listed = ", ".join(a.name)
        resp = input(f"Remove {listed} from tracking? [y/N] ").strip().lower()
        if resp not in ("y", "yes"):
            print("aborted")
            return 1
    for n in a.name:
        del cfg["services"][n]
        print(f"removed '{n}'")
    save_config(cfg)

    # drop it from the cache too, so a stale card can't reappear
    try:
        from .core import _read_cache, _write_cache
        c = _read_cache()
        for n in a.name:
            c.pop(n, None)
        _write_cache(c)
    except Exception:
        pass

    # Nudge the widgets so a removed card doesn't linger until the next tick.
    try:
        from .remove_ui import _refresh_widgets
        _refresh_widgets()
    except Exception:
        pass
    return 0


def cmd_enable(a) -> int:
    cfg = load_config()
    if a.name not in cfg["services"]:
        print(f"error: '{a.name}' is not tracked", file=sys.stderr)
        return 1
    cfg["services"][a.name]["enabled"] = (a.cmd == "enable")
    save_config(cfg)
    print(f"{a.name} {'enabled' if a.cmd == 'enable' else 'disabled'}")
    return 0


def cmd_set(a) -> int:
    cfg = load_config()
    if a.name not in cfg["services"]:
        print(f"error: '{a.name}' is not tracked. Add it first.", file=sys.stderr)
        return 1
    vals = _kv(a.pairs)
    if not vals:
        print("error: nothing to set (expected key=value)", file=sys.stderr)
        return 1
    for k, v in vals.items():
        cfg["services"][a.name][k] = v
        if k in ("credits", "credits_total", "used", "limit"):
            cfg["services"][a.name]["updated"] = time.strftime("%Y-%m-%d")
        shown = "***" if any(t in k.lower() for t in ("token", "key", "secret")) else v
        print(f"{a.name}.{k} = {shown}")
    save_config(cfg)
    return 0


def cmd_list(a) -> int:
    cfg = load_config()
    if a.json:
        json.dump(cfg, sys.stdout, indent=2)
        print()
        return 0
    if not cfg["services"]:
        print("nothing tracked yet — try: aiquota add claude")
        return 0
    print(C.bold(f"Tracked services  {C.dim(config_path())}\n"))
    from .core import is_linked
    for name, s in cfg["services"].items():
        state = "" if s.get("enabled", True) else C.dim("  (disabled)")
        link = (C.green("  linked") if is_linked(s)
                else C.yellow("  not linked"))
        print(f"  {C.cyan(name):<20} adapter={s.get('adapter', name)}{link}{state}")
    return 0


def cmd_link(a) -> int:
    """Browse every known AI platform and add the ones you use.

    Shows the full catalog — not just what's installed — so you can see what
    exists. Nothing is read or sent until you pick an entry and confirm.
    """
    from .catalog import by_key, sorted_catalog

    load_adapters()
    cfg = load_config()
    reg = registry()
    # "tracked" must mean genuinely LINKED — a bare config entry is not.
    from .core import linked_services
    tracked = linked_services(cfg)

    entries = sorted_catalog()
    if getattr(a, "name", None):
        entries = [e for e in entries if e["key"] == a.name
                   or a.name.lower() in e["name"].lower()]
        if not entries:
            print(f"error: '{a.name}' is not in the catalog. "
                  "Run `aiquota link` to see everything.", file=sys.stderr)
            return 1

    print(C.bold("\nAdd an AI account\n"))
    print(C.dim("Nothing is read until you choose it.\n"))

    options: List[Dict[str, Any]] = []
    BADGE = {
        "live": lambda: C.green("● live"),
        "soon": lambda: C.yellow("◐ manual for now"),
        "manual": lambda: C.dim("○ manual"),
    }

    for e in entries:
        ad = reg.get(e["adapter"])
        found = []
        if ad and e["support"] == "live":
            try:
                found = ad.detect() or []
            except Exception:
                found = []

        options.append({"entry": e, "found": found})
        n = len(options)
        state = C.green("  ✓ tracked") if e["key"] in tracked else ""
        badge = BADGE.get(e["support"], lambda: "")()
        print(f"  {C.bold('[' + str(n) + ']'):<6} {C.cyan(e['name']):<24} "
              f"{badge}{state}")
        print(C.dim(f"         {e['note']}"))
        if found:
            for f in found:
                print(C.green(f"         ✓ found: {f['detail']}"))
        elif e["support"] == "live":
            print(C.dim(f"         needs: {e['login']}"))
        print()

    # Always offer an escape hatch for platforms not in the catalog.
    options.append({"entry": {"key": "", "name": "Something else",
                              "adapter": "manual", "support": "manual",
                              "note": "any service not listed above",
                              "login": "wherever it shows your usage"},
                    "found": []})
    print(f"  {C.bold('[' + str(len(options)) + ']'):<6} "
          f"{C.cyan('Something else…'):<24} {C.dim('○ manual')}")
    print(C.dim("         any AI service not listed above"))
    print()

    if a.list_only:
        print(C.dim("Run `aiquota link` (without --list) to add one.\n"))
        return 0

    try:
        raw = input("Add which? (number, or Enter to cancel): ").strip()
    except EOFError:
        raw = ""
    if not raw:
        print("cancelled — nothing added")
        return 0
    if not raw.isdigit() or not (1 <= int(raw) <= len(options)):
        print("error: not a valid choice", file=sys.stderr)
        return 1

    chosen = options[int(raw) - 1]
    e, found = chosen["entry"], chosen["found"]
    key = e["key"]

    # ---- live path: a real credential was found, ask before using it -----
    if found:
        f = found[0]
        print()
        print(f"This will let aiquota read {C.bold(f['source'])}")
        print(C.dim(f"  {f['detail']}"))
        ad = reg.get(e["adapter"])
        if ad and ad.cost_note:
            print(C.yellow(f"  Note: {ad.cost_note}"))
        try:
            ok = input("Link it? [y/N] ").strip().lower()
        except EOFError:
            ok = ""
        if ok not in ("y", "yes"):
            print("cancelled — nothing added")
            return 0
        entry = cfg["services"].get(key, {})
        entry.update({"adapter": e["adapter"], "enabled": True})
        entry.update(f.get("config") or {})
        plan = input("Plan label (optional, e.g. 'Max'): ").strip()
        if plan:
            entry["plan"] = plan
        cfg["services"][key] = entry
        save_config(cfg)
        print(C.green(f"\n✓ linked {e['name']}"))
        print(C.dim(f"  run `aiquota` to see it · `aiquota unlink {key}` to undo"))
        return 0

    # ---- live adapter but nothing found: explain, don't fake it ----------
    if e["support"] == "live":
        print()
        print(C.yellow(f"No {e['name']} credential found on this machine."))
        print(C.dim(f"  {e['login']}"))
        print(C.dim("  Set it up, then run `aiquota link` again."))
        return 0

    # ---- manual path: track it with numbers the USER provides ------------
    print()
    print(f"{C.bold(e['name'])} has no usage API — {e['note']}")
    print(C.dim(f"  Check yours at: {e['login']}"))
    print(C.dim("  Enter what you see there, or press Enter to skip a field.\n"))

    entry: Dict[str, Any] = {"adapter": "manual", "enabled": True,
                             "service": e["name"]}
    # "Something else" has no catalog key — ask for the name.
    if not key:
        try:
            typed = input("Service name: ").strip()
        except EOFError:
            typed = ""
        if not typed:
            print("cancelled")
            return 0
        key = typed.lower().replace(" ", "-")
        entry["service"] = typed.replace("-", " ").replace("_", " ").title()

    try:
        plan = input("Plan label (optional): ").strip()
        credits = input("Credits / units remaining (optional): ").strip()
        total = input("Total per period (optional): ").strip()
        renews = input("Renews on YYYY-MM-DD (optional): ").strip()
    except EOFError:
        print("cancelled")
        return 0

    if plan:
        entry["plan"] = plan
    if credits:
        entry["credits"] = _coerce(credits)
    if total:
        entry["credits_total"] = _coerce(total)
    if renews:
        entry["renews_on"] = renews
    if not credits and not renews:
        entry["note"] = "Added — run `aiquota set %s credits=…` to fill in" % key
    entry["updated"] = time.strftime("%Y-%m-%d")
    cfg["services"][key] = entry
    save_config(cfg)
    print(C.green(f"\n✓ added {entry['service']} (manual)"))
    print(C.dim(f"  update anytime: aiquota set {key} credits=…"))
    return 0


def cmd_unlink(a) -> int:
    """Stop using a linked credential, keeping the service configured."""
    cfg = load_config()
    if a.name not in cfg.get("services", {}):
        print(f"error: '{a.name}' is not tracked", file=sys.stderr)
        return 1
    entry = cfg["services"][a.name]
    removed = [k for k in ("autodiscover", "token_files", "token",
                           "auth_files", "account_id") if k in entry]
    for k in removed:
        entry.pop(k)
    save_config(cfg)
    try:
        from .core import _read_cache, _write_cache
        c = _read_cache()
        c.pop(a.name, None)
        _write_cache(c)
    except Exception:
        pass
    if removed:
        print(f"unlinked '{a.name}' (cleared: {', '.join(removed)})")
    else:
        print(f"'{a.name}' had no linked credentials")
    print(C.dim("  the service is still tracked; re-link with "
                f"`aiquota link {a.name}`"))
    return 0


def cmd_doctor(a) -> int:
    load_adapters(verbose=True)
    cfg = load_config()
    print(C.bold("aiquota doctor\n"))
    print(f"  config      {config_path()}")
    print(f"  adapters    {user_adapter_dir()}")
    print(f"  registered  {', '.join(sorted(registry())) or 'none'}")
    print(f"  tracked     {len(cfg.get('services', {}))}\n")

    # Entries added before an adapter existed stay stuck on manual and quietly
    # show "no values entered yet" while a live reader goes unused.
    from .core import stale_entries
    stale = stale_entries(cfg)
    if stale:
        print(C.bold("  upgradeable"))
        for key, adapter in stale.items():
            print(f"    {key:<12} stored as manual, but '{adapter}' can read "
                  f"it live\n{'':<17}fix: aiquota remove {key} -y && "
                  f"aiquota link {key}")
        print()

    d = collect(force=True, ttl=0)
    for s in d["services"]:
        label, colour = TIER_LABEL.get(s["tier"], ("?", C.dim))
        line = f"  {s['name']:<14} {colour(label)}"
        if s.get("error"):
            line += f"  {C.red(s['error'])}"
        elif s.get("windows"):
            line += f"  {len(s['windows'])} window(s)"
        print(line)
    return 0


# --------------------------------------------------------------- main

def build_parser() -> argparse.ArgumentParser:
    # Global flags live on a parent parser so they're accepted both before
    # and after the subcommand (`aiquota --json status` and `aiquota status --json`).
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--color", choices=["auto", "always", "never"],
                        default="auto")
    common.add_argument("-v", "--verbose", action="store_true")

    p = argparse.ArgumentParser(
        prog="aiquota", parents=[common],
        description="See how much of every AI subscription you've used, in one place.")
    sub = p.add_subparsers(dest="cmd")

    s = sub.add_parser("status", parents=[common],
                       help="show quota for all services (default)")
    s.add_argument("service", nargs="*", help="limit to these services")
    s.add_argument("--json", action="store_true")
    s.add_argument("--compact", action="store_true", help="one line for a status bar")
    s.add_argument("--html", metavar="PATH", help="also write an HTML widget")
    s.add_argument("--logos", action="store_true",
                   help="include each service's logo as a data URI (for widgets)")
    s.add_argument("-r", "--refresh", action="store_true", help="bypass cache")
    s.add_argument("--ttl", type=int, default=300, help="cache seconds (default 300)")
    s.add_argument("--exit-code", action="store_true",
                   help="exit 2 if any window exceeds --threshold")
    s.add_argument("--threshold", type=float, default=80.0)
    s.set_defaults(fn=cmd_status)

    a = sub.add_parser("add", parents=[common], help="track a new service")
    a.add_argument("name")
    a.add_argument("--adapter", help="adapter to use (default: same as name)")
    a.add_argument("--plan", help="display label, e.g. 'Max 20x'")
    a.add_argument("--set", action="append", metavar="K=V")
    a.add_argument("--force", action="store_true")
    a.set_defaults(fn=cmd_add)

    r = sub.add_parser("remove", aliases=["rm"], parents=[common], help="stop tracking a service")
    r.add_argument("name", nargs="+")
    r.add_argument("-y", "--yes", action="store_true", help="skip confirmation")
    r.set_defaults(fn=cmd_remove)

    for c in ("enable", "disable"):
        e = sub.add_parser(c, parents=[common], help=f"{c} a tracked service")
        e.add_argument("name")
        e.set_defaults(fn=cmd_enable, cmd=c)

    st = sub.add_parser("set", parents=[common], help="set a config value (credits, tokens, dates)")
    st.add_argument("name")
    st.add_argument("pairs", nargs="+", metavar="K=V")
    st.set_defaults(fn=cmd_set)

    ls = sub.add_parser("list", parents=[common], help="list tracked services")
    ls.add_argument("--json", action="store_true")
    ls.set_defaults(fn=cmd_list)

    ad = sub.add_parser("adapters", parents=[common], help="list available adapters")
    ad.add_argument("--json", action="store_true")
    ad.set_defaults(fn=cmd_adapters)

    lk = sub.add_parser("link", parents=[common],
                        help="interactively link an AI account (asks first)")
    lk.add_argument("name", nargs="?", help="limit to one adapter")
    lk.add_argument("--list", dest="list_only", action="store_true",
                    help="only show what could be linked; change nothing")
    lk.set_defaults(fn=cmd_link)

    ul = sub.add_parser("unlink", parents=[common],
                        help="stop using a linked credential")
    ul.add_argument("name")
    ul.set_defaults(fn=cmd_unlink)

    dr = sub.add_parser("doctor", parents=[common], help="diagnose configuration problems")
    dr.set_defaults(fn=cmd_doctor)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    p = build_parser()

    KNOWN = {"status", "add", "remove", "rm", "enable", "disable",
             "set", "list", "adapters", "doctor", "link", "unlink"}
    HELP = {"-h", "--help"}

    # `aiquota`, `aiquota --color always`, `aiquota claude` all mean "status".
    # Only inject when no real subcommand appears anywhere in argv.
    if not (set(argv) & HELP) and not any(t in KNOWN for t in argv):
        argv = ["status"] + argv

    a = p.parse_args(argv)
    C.on = _use_colour(a.color)
    if not getattr(a, "fn", None):
        p.print_help()
        return 0
    try:
        return a.fn(a)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
