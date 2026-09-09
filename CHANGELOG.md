# Changelog

## 0.2.1 — 2026-09-09

**Removed Midjourney and Suno sign-in.** Both adapters worked. Both are gone.

Competitive research turned up something I should have checked before
shipping them: these two providers explicitly prohibit automated access, in
language they enforce with account blocks.

- Midjourney lists "Unauthorized automation & third party apps are not
  allowed" as one of four Community Guidelines rules: *"automating
  interactions with Midjourney service is strictly prohibited... Accounts who
  do not comply with these rules may be blocked."*
- Suno's terms forbid *"any data mining, robots, scraping, or similar data
  gathering or extraction methods"* (clause 13). Polling a billing endpoint
  on a schedule is exactly that.

I had verified that neither carried Anthropic's specific OAuth restriction
and treated that as sufficient. It wasn't — I checked the wrong clause. Both
are now manual entry, their endpoint URLs are gone from the codebase, and
tests fail if anyone re-adds an adapter for either.

The README now separates "no endpoint exists" from "the provider forbids
reading it", because those are very different statements and collapsing them
hid the more important one.

Sign-in platforms: 7 → 5 (Cursor, Grok, OpenRouter, Perplexity, Runway).

## 0.2.0 — 2026-09-09

The release that made aiquota installable, and made "add an account" mean
signing in rather than pasting a key.

### Install

- **`aiquota install-widget`** places the menu bar and desktop widgets for
  you. Previously the widgets shipped only in the git repo, so
  `pip install aiquota` gave you a CLI and nothing else — the real setup was
  "clone the repo and copy four files by hand".
- Widget sources now ship inside the package.
- The installer rewrites the SwiftBar plugin's `PATH` to wherever *this*
  aiquota lives, so pipx and venv installs work. The previous hard-coded
  guesses covered only `~/.local/bin` and Homebrew.
- Missing host apps are reported with the `brew` command instead of being
  ignored; non-macOS exits with a clear message.
- Added `--version`.

### Signing in

- **Browser sign-in**: pick a platform and its own login page opens. You
  choose the account; aiquota never sees a password and never asks for one.
- Live for **Cursor, Suno, Grok, Runway, OpenRouter, Perplexity, Midjourney**.
- Perplexity and Midjourney are read with an in-page `fetch()`, because
  Cloudflare fingerprints the TLS handshake and Midjourney's host refuses
  Python's TLS outright. A stdlib client cannot reach either.
- **`login_policy.py`** records, per provider, whether third-party sign-in is
  permitted, why, and the source. Anthropic restricts OAuth to its own apps
  and banned third-party tools' users in April 2026, so Claude deliberately
  cannot offer it — enforced by tests, not by memory.

### Reading quota

- Claude now tries the read-only `/api/oauth/usage` endpoint **before** the
  `/v1/messages` header route. The old order spent quota to measure quota and
  produced exactly the traffic Anthropic polices.
- Any usage bucket may be `null`, and `resets_at` may be null independently —
  both are nil-checked. `extra_usage` is in cents and converted.
- ChatGPT recovers `account_id` from the `id_token` when `auth.json` has it as
  null, which is common; without it the usage endpoint answers for the wrong
  workspace.

### Interface

- Platform logos in the widgets, the picker, and the dialogs.
- Dialogs redesigned to match the widget — real heading, detail rows, the
  platform's own icon, macOS buttons — instead of unstyled AppleScript alerts.
  AppleScript remains the fallback where no browser exists.
- Remove a platform from the widget: hover a card, click ×, confirm.
- Meters are white; red is reserved for ≥85%, so colour means something.
- Every window shows its own percentage. The headline number is gone: it was
  whichever window happened to be highest, so it silently changed meaning
  between services.
- Widget background composites over an opaque base — at high transparency a
  hard wallpaper edge sliced the panel in half.
- Widget is draggable, and its position survives refreshes.

### Fixed

- The picker opened, then closed itself ~200ms later: any request to the
  loopback server counted as a selection, and Chrome automatically fetches
  `/favicon.ico`.
- "Add account" appeared dead from the menu bar: `osascript` run from a
  non-GUI process silently auto-answers dialogs instead of showing them.
  All dialogs now go through Finder.
- The remove button did nothing: AppleScript built inside a JS string inside
  a shell command lost its quoting. Removal is now one plain argument to one
  binary.
- A removed card lingered for up to five minutes; removal now nudges the
  widget to redraw.
- "Added" meant "present in config.json", so a fresh install claimed Claude
  and ChatGPT were already linked.
- Widget went blank when logos were added — the payload grew past what
  Übersicht reliably passes to `render()`. Logos are baked into the widget
  instead.

## 0.1.0 — 2026-09-08

First release. CLI, Claude and ChatGPT adapters, manual entry, menu bar and
desktop widgets, adapter registry for third-party plugins.
