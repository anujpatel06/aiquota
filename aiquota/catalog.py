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
        "adapter": "manual",
        "support": "manual",
        "note": "Pro search credits; no public usage endpoint",
        "login": "perplexity.ai → Settings",
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
        "note": "Fast GPU minutes — visible via /info, no API",
        "login": "midjourney.com → Manage Sub",
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
        "adapter": "suno",
        "support": "live",
        "note": "Song credits and renewal date (sign in)",
        "login": "Sign in with your own account — no API key",
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
