"""Catalog of major AI platforms.

`aiquota link` shows this whole list — not just what happens to be installed —
so you can browse everything and pick what to track.

Honesty is the point of the `support` field. Most AI platforms publish no
usage API at all; pretending otherwise would be the same failure as inventing
numbers. Each entry states plainly what you can actually get:

  live    an adapter fetches real usage once you link a credential
  manual  no usage API exists; you enter the numbers yourself
  soon    an adapter is planned/possible but not written yet

Adding a platform here does NOT make it fetchable. If you know of a real
endpoint for a `manual` entry, that's the most useful PR you can send.
"""
from __future__ import annotations

from typing import Any, Dict, List

# adapter: which adapter handles it ("manual" when nothing can be fetched)
# support: live | manual | soon
# note:    what the user actually gets, in one line
CATALOG: List[Dict[str, Any]] = [
    {
        "key": "claude",
        "domain": "claude.ai",
        "name": "Claude",
        "vendor": "Anthropic",
        "adapter": "claude",
        "support": "live",
        "note": "Pro/Max 5-hour + weekly windows, reset times",
        "login": "Claude Code login, or an OAuth token",
    },
    {
        "key": "chatgpt",
        "domain": "openai.com",
        "name": "ChatGPT / Codex",
        "vendor": "OpenAI",
        "adapter": "chatgpt",
        "support": "live",
        "note": "Codex/Work windows + credits (NOT general chat quota)",
        "login": "Codex CLI login (~/.codex/auth.json)",
    },
    {
        "key": "cursor",
        "domain": "cursor.com",
        "name": "Cursor",
        "vendor": "Anysphere",
        "adapter": "cursor",
        "support": "live",
        "note": "Request quota for the billing period (sign in)",
        "login": "Sign in with your own account — no API key",
    },
    {
        "key": "copilot",
        "domain": "github.com",
        "name": "GitHub Copilot",
        "vendor": "GitHub",
        "adapter": "copilot",
        "support": "live",
        "note": "Plan + premium request quota (reuses your gh CLI login)",
        "login": "gh auth login — no key pasting",
    },
    {
        "key": "gemini",
        "domain": "gemini.google.com",
        "name": "Gemini",
        "vendor": "Google",
        "adapter": "manual",
        "support": "manual",
        "note": "No consumer quota API (Gemini CLI's login is Cloud-scoped only)",
        "login": "gemini.google.com",
    },
    {
        "key": "perplexity",
        "domain": "perplexity.ai",
        "name": "Perplexity",
        "vendor": "Perplexity",
        "adapter": "perplexity",
        "support": "live",
        "note": "Pro search quota (sign in)",
        "login": "Sign in with your own account — no API key",
    },
    {
        "key": "grok",
        "domain": "x.ai",
        "name": "Grok",
        "vendor": "xAI",
        "adapter": "grok",
        "support": "live",
        "note": "Subscription tier (sign in)",
        "login": "Sign in with your own account — no API key",
    },
    {
        "key": "midjourney",
        "domain": "midjourney.com",
        "name": "Midjourney",
        "vendor": "Midjourney",
        "adapter": "manual",
        "support": "manual",
        "note": "Fast GPU minutes — enter manually (MJ forbids automation)",
        "login": "Provider prohibits automated access — values are yours to enter",
    },
    {
        "key": "higgsfield",
        "domain": "higgsfield.ai",
        "name": "Higgsfield",
        "vendor": "Higgsfield",
        "adapter": "manual",
        "support": "manual",
        "note": "Credits are dashboard-only; API has no balance endpoint",
        "login": "higgsfield.ai → avatar → Manage Account",
    },
    {
        "key": "runway",
        "domain": "runwayml.com",
        "name": "Runway",
        "vendor": "Runway",
        "adapter": "runway",
        "support": "live",
        "note": "Credit balance (sign in)",
        "login": "Sign in with your own account — no API key",
    },
    {
        "key": "elevenlabs",
        "domain": "elevenlabs.io",
        "name": "ElevenLabs",
        "vendor": "ElevenLabs",
        "adapter": "elevenlabs",
        "support": "live",
        "note": "Character quota + reset date (official API — needs a key)",
        "login": "elevenlabs.io → avatar → API Key (no OAuth for third-party apps)",
    },
    {
        "key": "openrouter",
        "domain": "openrouter.ai",
        "name": "OpenRouter",
        "vendor": "OpenRouter",
        "adapter": "openrouter",
        "support": "live",
        "note": "Credit balance and spend (official API)",
        "login": "openrouter.ai → Keys",
    },
    {
        "key": "suno",
        "domain": "suno.com",
        "name": "Suno",
        "vendor": "Suno",
        "adapter": "manual",
        "support": "manual",
        "note": "Credits — enter manually (Suno forbids automated access)",
        "login": "Provider prohibits automated access — values are yours to enter",
    },
    {
        "key": "v0",
        "domain": "v0.app",
        "name": "v0",
        "vendor": "Vercel",
        "adapter": "manual",
        "support": "manual",
        "note": "Message credits; no public usage endpoint",
        "login": "v0.app → Settings → Billing",
    },
    {
        "key": "lovable",
        "domain": "lovable.dev",
        "name": "Lovable",
        "vendor": "Lovable",
        "adapter": "manual",
        "support": "manual",
        "note": "Daily/monthly message credits; no public API",
        "login": "lovable.dev → Settings",
    },
    {
        "key": "replit",
        "domain": "replit.com",
        "name": "Replit",
        "vendor": "Replit",
        "adapter": "manual",
        "support": "manual",
        "note": "Agent checkpoints / cycles; no public usage API",
        "login": "replit.com → Account → Usage",
    },
    {
        "key": "deepseek",
        "name": "DeepSeek",
        "vendor": "DeepSeek",
        "adapter": "deepseek",
        "support": "live",
        "note": "Prepaid balance",
        "login": "platform.deepseek.com → API keys",
        "domain": "deepseek.com",
    },
    {
        "key": "poe",
        "name": "Poe",
        "vendor": "Poe",
        "adapter": "poe",
        "support": "live",
        "note": "Compute points remaining",
        "login": "poe.com/api_key",
        "domain": "poe.com",
    },
    {
        "key": "fal",
        "name": "fal.ai",
        "vendor": "fal.ai",
        "adapter": "fal",
        "support": "live",
        "note": "Credit balance",
        "login": "fal.ai/dashboard/keys",
        "domain": "fal.ai",
    },
    {
        "key": "heygen",
        "name": "HeyGen",
        "vendor": "HeyGen",
        "adapter": "heygen",
        "support": "live",
        "note": "Video credits",
        "login": "app.heygen.com → Settings → API",
        "domain": "heygen.com",
    },
    {
        "key": "leonardo",
        "name": "Leonardo.ai",
        "vendor": "Leonardo.ai",
        "adapter": "leonardo",
        "support": "live",
        "note": "Tokens and renewal date",
        "login": "app.leonardo.ai → API Access",
        "domain": "leonardo.ai",
    },
    {
        "key": "recraft",
        "name": "Recraft",
        "vendor": "Recraft",
        "adapter": "recraft",
        "support": "live",
        "note": "Credit balance",
        "login": "recraft.ai → Profile → API",
        "domain": "recraft.ai",
    },
    {
        "key": "kling",
        "name": "Kling",
        "vendor": "Kling",
        "adapter": "kling",
        "support": "live",
        "note": "Resource pack quota",
        "login": "klingai.com → API console",
        "domain": "klingai.com",
    },
    {
        "key": "zai",
        "name": "Z.ai",
        "vendor": "Z.ai",
        "adapter": "zai",
        "support": "live",
        "note": "5-hour, weekly and monthly windows",
        "login": "z.ai → API keys",
        "domain": "z.ai",
    },
    {
        "key": "udio",
        "name": "Udio",
        "vendor": "Udio",
        "adapter": "manual",
        "support": "manual",
        "note": "Credits — enter manually (Udio prohibits automated access)",
        "login": "",
        "domain": "udio.com",
    },
    {
        "key": "luma",
        "name": "Luma",
        "vendor": "Luma",
        "adapter": "manual",
        "support": "manual",
        "note": "Credits — enter manually (Luma prohibits automated access)",
        "login": "",
        "domain": "lumalabs.ai",
    },
    {
        "key": "descript",
        "name": "Descript",
        "vendor": "Descript",
        "adapter": "manual",
        "support": "manual",
        "note": "Hours — enter manually (Descript prohibits automated access)",
        "login": "",
        "domain": "descript.com",
    },
    {
        "key": "bolt",
        "name": "Bolt.new",
        "vendor": "Bolt.new",
        "adapter": "manual",
        "support": "manual",
        "note": "Tokens — enter manually (StackBlitz prohibits automated access)",
        "login": "",
        "domain": "bolt.new",
    },
]

SUPPORT_ORDER = {"live": 0, "soon": 1, "manual": 2}


def by_key(key: str):
    for e in CATALOG:
        if e["key"] == key:
            return e
    return None


def sorted_catalog() -> List[Dict[str, Any]]:
    return sorted(CATALOG, key=lambda e: (SUPPORT_ORDER.get(e["support"], 9),
                                          e["name"].lower()))
