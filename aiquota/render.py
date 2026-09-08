"""Standalone HTML widget renderer.

Emits a self-contained page that adapts to a light or dark host via
prefers-color-scheme, and honours CSS variables if the embedder sets them.
"""
from __future__ import annotations

import html
import time
from typing import Any, Dict

TIER_CLASS = {"live": "ok", "local": "warn", "manual": "dim",
              "unconfigured": "warn", "error": "bad"}
TIER_TEXT = {"live": "live", "local": "estimate", "manual": "manual",
             "unconfigured": "setup needed", "error": "error"}


def render_html(d: Dict[str, Any], title: str = "AI Quota") -> str:
    cards = []
    for s in d.get("services", []):
        tier = s.get("tier", "manual")
        cls, txt = TIER_CLASS.get(tier, "dim"), TIER_TEXT.get(tier, tier)
        esc = html.escape

        bars = ""
        for w in s.get("windows", []):
            pct = max(0.0, min(100.0, float(w["used_pct"])))
            tone = "bad" if pct >= 85 else ("warn" if pct >= 60 else "ok")
            reset = (f"<span class='rs'>{esc(str(w['resets_at']))}</span>"
                     if w.get("resets_at") else "")
            bars += (f"<div class='w'><div class='wl'><span>{esc(w['label'])}</span>"
                     f"<span class='wp'>{pct:.0f}%{reset}</span></div>"
                     f"<div class='bar'><span class='{tone}' "
                     f"style='width:{pct:.1f}%'></span></div></div>")

        ex = s.get("extra") or {}
        body = bars
        if not bars:
            big = ""
            if ex.get("credits") is not None:
                big = (f"<div class='big'>{esc(str(ex['credits']))}"
                       f"<span> credits</span></div>")
            elif ex.get("renews_in_days") is not None:
                big = (f"<div class='big'>{ex['renews_in_days']}"
                       f"<span> days to renewal</span></div>")
            msg = s.get("error") or s.get("note") or "No data"
            body = big + f"<div class='msg'>{esc(str(msg))}</div>"
        else:
            meta = []
            if ex.get("credits") is not None:
                meta.append(f"{esc(str(ex['credits']))} credits")
            if ex.get("renews_in_days") is not None:
                meta.append(f"renews in {ex['renews_in_days']}d")
            if s.get("error"):
                meta.append(esc(str(s["error"])))
            if meta:
                body += f"<div class='msg'>{' · '.join(meta)}</div>"

        plan = s.get("plan") or ""
        sub = (f"<div class='sp'>{esc(plan)}</div>"
               if plan and plan != s.get("service") else "")
        cards.append(
            f"<div class='svc'><div class='sh'><div>"
            f"<div class='sn'>{esc(s.get('service', ''))}</div>{sub}</div>"
            f"<span class='badge {cls}'>{txt}</span></div>{body}</div>")

    gen = time.strftime("%H:%M", time.localtime(d.get("generated_at", time.time())))
    n_live = sum(1 for s in d.get("services", []) if s.get("tier") == "live")
    foot = f"{len(d.get('services', []))} tracked · {n_live} live · {gen}"

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<meta name="viewport" content="width=device-width,initial-scale=1"><style>
 :root {{ --fg:#1a1a1a; --muted:#666; --border:#e3e3e3; --card:#fff; --accent:#666; }}
 @media (prefers-color-scheme: dark) {{
   :root {{ --fg:#e6e6e6; --muted:#8b949e; --border:#30363d; --card:#161b22; }}
 }}
 * {{ box-sizing:border-box }}
 body {{ margin:0; padding:14px; color:var(--foreground,var(--fg));
   background:transparent;
   font-family:var(--font,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif); }}
 .head {{ display:flex; align-items:baseline; gap:.6rem; margin-bottom:.85rem; flex-wrap:wrap }}
 .head h2 {{ margin:0; font-size:1rem; font-weight:600; letter-spacing:-.01em }}
 .head .sub {{ color:var(--muted-foreground,var(--muted)); font-size:.78rem }}
 .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(215px,1fr)); gap:.6rem }}
 .svc {{ border:1px solid var(--border); border-radius:10px; padding:.75rem .8rem;
   background:var(--card) }}
 .sh {{ display:flex; justify-content:space-between; align-items:flex-start;
   gap:.5rem; margin-bottom:.6rem }}
 .sn {{ font-weight:600; font-size:.88rem }}
 .sp {{ font-size:.7rem; color:var(--muted-foreground,var(--muted)); margin-top:.05rem }}
 .badge {{ font-size:.6rem; text-transform:uppercase; letter-spacing:.06em;
   padding:.15rem .4rem; border-radius:4px; border:1px solid var(--border);
   color:var(--muted-foreground,var(--muted)); white-space:nowrap }}
 .badge.ok {{ color:#3fb950; border-color:#3fb95055 }}
 .badge.warn {{ color:#d29922; border-color:#d2992255 }}
 .badge.bad {{ color:#f85149; border-color:#f8514955 }}
 .w {{ margin-bottom:.5rem }}
 .wl {{ display:flex; justify-content:space-between; font-size:.72rem;
   margin-bottom:.25rem; gap:.5rem }}
 .wl span:first-child {{ color:var(--muted-foreground,var(--muted)) }}
 .wp {{ font-variant-numeric:tabular-nums; font-weight:600 }}
 .rs {{ font-weight:400; color:var(--muted-foreground,var(--muted));
   margin-left:.35rem; font-size:.68rem }}
 .bar {{ height:5px; border-radius:3px; background:var(--border); overflow:hidden }}
 .bar span {{ display:block; height:100%; border-radius:3px; background:var(--accent) }}
 .bar span.ok {{ background:#3fb950 }} .bar span.warn {{ background:#d29922 }}
 .bar span.bad {{ background:#f85149 }}
 .big {{ font-size:1.3rem; font-weight:600; letter-spacing:-.02em; margin:.15rem 0 .1rem }}
 .big span {{ font-size:.68rem; font-weight:400;
   color:var(--muted-foreground,var(--muted)); letter-spacing:0 }}
 .msg {{ font-size:.7rem; color:var(--muted-foreground,var(--muted));
   line-height:1.4; margin-top:.3rem }}
 .foot {{ margin-top:.85rem; padding-top:.6rem; border-top:1px solid var(--border);
   font-size:.71rem; color:var(--muted-foreground,var(--muted)) }}
</style></head><body>
 <div class="head"><h2>{html.escape(title)}</h2>
   <span class="sub">subscription quota</span></div>
 <div class="grid">{''.join(cards)}</div>
 <div class="foot">{foot}</div>
</body></html>"""


def write_html(d: Dict[str, Any], path: str, title: str = "AI Quota") -> str:
    with open(path, "w") as f:
        f.write(render_html(d, title))
    return path
