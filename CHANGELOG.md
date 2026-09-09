# Changelog

## 0.5.0 — 2026-09-09

The four gaps found by reading CodexBar's source, closed.

### Native menu bar app
`AIQuotaBar.app` — SwiftUI `MenuBarExtra`, 252KB, no SwiftBar or Ubersicht
required. Builds with `bash scripts/build_app.sh`; no Xcode needed, just the
Swift toolchain.

It shells out to `aiquota status --json` rather than reimplementing anything,
so provider logic, credential handling and the honesty rules stay in one
place instead of drifting across two codebases. It also asks
`aiquota refresh --json` for its poll interval, so the adaptive policy is not
duplicated either.

Ad-hoc signed. Developer ID signing and notarization need a paid Apple
account; until then Gatekeeper asks on first open, and the README says so
rather than pretending otherwise.

### `aiquota serve`
A read-only HTTP API on localhost so other tools consume aiquota instead of
cloning it: `/usage`, `/usage/<name>`, `/providers`, `/healthz`.

Binds 127.0.0.1 only and refuses a public bind outright. No endpoint can
change configuration, and a test asserts no endpoint leaks a credential.
Honours the same TTL cache, so a chatty client cannot make aiquota hammer a
provider.

### Cost tracking
A percentage answers "how much of my allowance is gone". It cannot answer
"what will I be billed". Providers that report real money now populate a
`Cost` — balance, limit, currency, period — shown in the CLI, the widget and
the native app.

`limit` stays optional: prepaid balances have no cap, and a percentage
against an invented ceiling would be a lie.

### VISION.md and CONTRIBUTING.md
What gets merged by default, what needs discussion, and the rules that don't
bend — with the note that those rules are enforced by tests, not honour.

162 tests.

## 0.4.1 — 2026-09-09

Performance, measured before and after rather than guessed at.

### Parallel probes
`collect()` ran providers one at a time, so a cold refresh cost the SUM of
every provider's latency — linking more accounts made the tool slower, which
is a bad trade for something whose selling point is breadth. Probes now run
in a bounded pool (8 workers).

Measured with 8 providers at 0.4s each: **3.2s -> 0.41s, a 7.8x speedup.**
Output order stays stable so the widget doesn't reshuffle its rows, one slow
provider no longer blocks the rest, and a crashing adapter still can't take
down the others.

### Faster startup
`urllib` was imported at module scope in the HTTP helper, dragging in the
whole `email` package for ~28ms on every invocation — including the cached
path that never makes a request. Now imported inside `request()`.

**Import cost: 0.13s -> 0.06s. Cached `aiquota status`: ~40ms.**

### Picker
Logos (65KB of JSON) were re-read and re-parsed on every call, on the exact
path the user waits for. Parsed once per process now.

## 0.4.0 — 2026-09-09

Ideas worth taking from CodexBar (21k stars, MIT), credited and adapted.

### Added — adaptive refresh
Checks widen from 2 min while you're looking to 30 min when nobody is, and
back off to 30 min in Low Power Mode. `aiquota refresh` prints the decision
and why. Polling a provider every minute while the user sleeps drains their
battery and is the kind of traffic that gets undocumented endpoints closed.

### Added — structured failure reasons
"HTTP 401" tells nobody anything. Failures now carry a kind, whether the user
can fix it, whether retrying helps, and what to actually do — surfaced as a
hint line under the error in the widget.

### Added — confidence, separate from tier
A reading can be live and still imprecise. `exact` means the provider gave
real counts; `percent_only` means it gave a percentage with no totals behind
it (Claude and ChatGPT both do this). Tier says where a number came from;
confidence says how precise it is.

### Fixed
`Result.from_dict` tolerates caches written by older versions instead of
raising on unknown fields.

## 0.3.0 — 2026-09-09

Coverage: 16 → 28 platforms.

### Added — 8 providers with documented, key-authenticated balance APIs
DeepSeek, Poe, fal.ai, HeyGen, Leonardo.ai, Recraft, Kling, Z.ai.

The safest class in the catalog: the provider publishes the endpoint, you
create the key in their own dashboard, and reading your balance is what the
endpoint is for. Every route was probed unauthenticated and answered 401
with a JSON error, so none of them are guesses.

### Added — consumer ChatGPT feature credits
Deep Research, image generation, file uploads and whatever else your account
meters, via `limits_progress` on `/backend-api/conversation/init`. Creates no
conversation and spends no quota.

Plain chat/GPT-5 message counts are **not** included, because no endpoint
reports them. Every extension claiming "X of Y messages left" counts locally
against a hard-coded plan table. A test now fails if that estimate ever
appears here.

### Added — Homebrew tap
```
brew install anujpatel06/aiquota/aiquota
```

### Excluded on ToS grounds
Udio, Luma, Descript and Bolt.new join Midjourney and Suno as manual-entry
only. Each prohibits automated access in terms with no carve-out for reading
your own account. Reasons and source URLs ship in the README.

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
