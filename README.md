# aiquota

**See how much of every AI subscription you've used — in one place.**

Checking whether you're about to hit a limit means opening Claude's settings,
then ChatGPT's, then whatever else you pay for. `aiquota` puts every quota in
one command.

```
$ aiquota

Claude  Max  [live]
  5-hour session     ████░░░░░░░░░░░░░░░░░░░░  16.0%  resets Wed 01:40
  Weekly (all)       ░░░░░░░░░░░░░░░░░░░░░░░░   2.0%  resets Mon 00:30
  binding: five_hour · overage: rejected

ChatGPT  ChatGPT (team)  [live]
  5-hour             █████████████░░░░░░░░░░░  53.0%  resets Tue 22:45
  7-day              ████░░░░░░░░░░░░░░░░░░░░  18.0%  resets Tue 11:39

Higgsfield  Creator  [manual]
  Credits used       ███████████████░░░░░░░░░  63.0%
  credits: 555 · renews in 22d
```

- **No dependencies.** Pure Python stdlib.
- **Honest about confidence.** Every card is tagged `live`, `manual`, or
  `error`, so you always know whether you're reading a real number or your own
  note.
- **Extensible.** Add a service with one config command, or a new provider by
  dropping a Python file in a directory.

---

## Install

```bash
uv tool install aiquota      # or: pipx install aiquota
aiquota install-widget       # macOS: adds the menu bar + desktop widgets
```

Then click **＋ Add an AI account** in the widget and sign in.

<details>
<summary>Other ways</summary>

```bash
pip install aiquota                 # into the current environment
pip install git+https://github.com/anujpatel06/aiquota   # latest main
```

`uv tool` / `pipx` are recommended because they put `aiquota` on your PATH
without touching your project environments.

The widgets need one of these host apps — `install-widget` tells you which
is missing rather than failing quietly:

```bash
brew install --cask swiftbar    # menu bar
brew install --cask ubersicht   # desktop
```

Install just one with `aiquota install-widget menubar` or `… desktop`.
</details>

Python 3.8+, no dependencies. The CLI runs anywhere; the widgets are macOS
only, and `install-widget` says so instead of pretending on Linux.

## Quick start

```bash
aiquota link      # see what's on your machine, choose what to track
aiquota           # show everything
```

`link` is the only way an account gets connected. It lists credentials it can
see — which account, from which file — and **links nothing until you pick one
and confirm**. Nothing is read or sent before that.

```
$ aiquota link

Add an AI account

Nothing is read until you choose it.

  [1]    ChatGPT / Codex          ● live  ✓ tracked
         Codex/Work windows + credits (NOT general chat quota)
         ✓ found: Codex CLI login (auth_mode: chatgpt), account 2754df98…

  [2]    Claude                   ● live
         Pro/Max 5-hour + weekly windows, reset times
         needs: Claude Code login, or an OAuth token

  [3]    Cursor                   ◐ manual for now
         Request quota is shown in-app; no documented API yet

  [7]    Gemini                   ○ manual
         No consumer quota API; AI Studio shows API-tier limits only

  ... 16 platforms total ...

  [17]   Something else…          ○ manual
         any AI service not listed above

Add which? (number, or Enter to cancel):
```

The badges are honest about what you'll actually get:

| Badge | Meaning |
|---|---|
| `● live` | An adapter fetches real usage once you link a credential |
| `◐ manual for now` | An endpoint likely exists; no adapter written yet — PRs welcome |
| `○ manual` | No usage API exists; you enter the numbers |

Most AI platforms publish no consumer usage API at all. Listing them as
`manual` is deliberate — a browsable list of everything you pay for beats a
short list of only what can be automated.

Useful variants:

```bash
aiquota link --list      # just browse, change nothing
aiquota link cursor      # jump straight to one platform
aiquota unlink chatgpt   # stop using the credential, keep the service
```

## Adding accounts

Click **＋ Add an AI account…** in the menu bar or desktop widget and a native
macOS list appears with every supported platform:

```
●  ChatGPT / Codex  —  live usage  ✓ added
●  Claude           —  live usage  ✓ added
◐  Cursor           —  manual for now
◐  ElevenLabs       —  manual for now
◐  GitHub Copilot   —  manual for now
◐  OpenRouter       —  manual for now
○  Gemini           —  manual entry
○  Grok             —  manual entry
○  Higgsfield       —  manual entry
○  Midjourney       —  manual entry
○  Perplexity       —  manual entry
○  Runway           —  manual entry
○  Suno             —  manual entry
○  v0 / Lovable / Replit …
＋  Something else…
```

Pick one and it walks you through the rest. No terminal required — though
`aiquota link` gives the same flow in the shell if you prefer.

The badges say what you actually get:

| Badge | Meaning |
|---|---|
| `● live` | Real usage, fetched once you link a credential |
| `◐ manual for now` | An endpoint likely exists; no adapter yet — PRs welcome |
| `○ manual` | No usage API; you enter the numbers |

Most AI platforms publish no consumer usage API. Listing them as `manual` is
deliberate — seeing everything you pay for in one place beats seeing only the
two that can be automated.

## Usage

```bash
aiquota                      # status for everything (default command)
aiquota claude               # just one service
aiquota --json               # machine-readable
aiquota --compact            # one line, for a status bar
aiquota --html ~/quota.html  # write a widget
aiquota -r                   # bypass the cache
aiquota doctor               # diagnose configuration problems
```

### Managing services

```bash
aiquota list                       # what you're tracking
aiquota add midjourney --adapter manual --plan "Standard"
aiquota set midjourney credits=120 credits_total=900
aiquota disable chatgpt            # keep config, hide the card
aiquota enable chatgpt
aiquota remove midjourney          # asks first
aiquota rm midjourney -y           # don't ask
aiquota rm a b c -y                # several at once
```

`remove` also purges that service's cache entry, so a deleted card can't
reappear from stale data.

### Tracking a service with no API

Most AI subscriptions expose nothing. Track them anyway — no code required:

```bash
aiquota add higgsfield --adapter manual --plan "Creator" \
    --set credits=555 --set credits_total=1500 --set renews_on=2026-10-01

# or as a used/limit pair with your own unit
aiquota add midjourney --adapter manual \
    --set used=140 --set limit=900 --set unit_label="Fast GPU min"
```

These render as `manual`, so you're never fooled into thinking a hand-typed
number was fetched live.

## Supported platforms

`aiquota link` lists all of these. Two fetch real usage; the rest are tracked
with numbers you enter, because their vendors publish no consumer usage API.

| Platform | Status | What you get |
|---|---|---|
| **Claude** (Anthropic) | ● live | 5-hour + weekly windows, resets, overage state |
| **ChatGPT / Codex** (OpenAI) | ● live | Codex/Work windows + credits |
| Cursor, GitHub Copilot, ElevenLabs, OpenRouter | ◐ manual for now | An endpoint likely exists — adapters welcome |
| Gemini, Grok, Perplexity, Midjourney, Higgsfield, Runway, Suno, v0, Lovable, Replit | ○ manual | No usage API; you enter the numbers |
| Anything else | ○ manual | "Something else…" in the picker |

Adding a platform to the catalog does **not** make it fetchable. If you know a
real endpoint for a `manual` entry, that's the most valuable PR you can send —
see [CONTRIBUTING.md](CONTRIBUTING.md).

### Important caveats

Read these before trusting a number.

- **No vendor offers a documented consumer-quota API.** Both live adapters use
  undocumented endpoints that OpenAI's and Anthropic's own clients call. They
  can break without notice. This project has no affiliation with either.
- **Claude's reading costs a sliver of quota.** The unified headers only appear
  on an actual inference response, so the adapter makes a 1-token Haiku call.
  Results are cached for 5 minutes by default — raise `--ttl` if you poll often.
- **ChatGPT covers the Codex/Work meter, not general chat.** Your normal
  conversation quota has no reachable endpoint. Nothing here can show it.
- **ChatGPT Plus ≠ OpenAI API.** Separate products, separate billing. The
  documented `/v1/usage` endpoints report API spend and know nothing about a
  Plus subscription.

### Credentials

**aiquota never uses a credential you haven't linked.** Run `aiquota link` to
see what's available and choose. It will find logins belonging to other apps
(Claude Code, Codex CLI, Hermes) but will not touch them until you say so.

| Adapter | Can link from |
|---|---|
| `claude` | `AIQUOTA_CLAUDE_TOKEN` / `ANTHROPIC_TOKEN` env, `~/.claude/.credentials.json`, `~/.hermes/.env` |
| `chatgpt` | `AIQUOTA_CODEX_TOKEN` env, `~/.codex/auth.json` |

Env vars and tokens you put in the config are used directly — you set those
deliberately. Reading *another application's* credential file always requires
`link` (or `autodiscover=true`). Set `AIQUOTA_NO_AUTODISCOVER=1` to block it
entirely. Config lives at `~/.config/aiquota/config.json`, chmod `0600`.

## Writing an adapter

Drop a `.py` file in `~/.config/aiquota/adapters/` — no fork, no reinstall:

```python
from aiquota import Adapter, Result, Window, register, LIVE

@register
class MyServiceAdapter(Adapter):
    name = "myservice"                    # config key
    service = "My Service"                # display name
    summary = "What this reads"           # shown by `aiquota adapters`
    setup = "Set MYSERVICE_TOKEN"         # shown when unconfigured

    def probe(self, conf):
        return Result(
            name=self.name, service=self.service, tier=LIVE,
            windows=[Window(label="Monthly", used_pct=42.0,
                            resets_at="Nov 1")],
        )
```

Then `aiquota add myservice`. The contract:

- **Never raise.** Catch your errors and return `tier=ERROR` with a readable
  message. A broken adapter must not take down the whole run (there's a test
  for this).
- **Be honest about `tier`** — `LIVE` only for numbers you actually fetched.
- **Declare `cost_note`** if probing spends quota or money.

PRs adding adapters are welcome.

## Scripting

```bash
# warn when any window passes 80%
aiquota --exit-code --threshold 80 || notify-send "AI quota running low"

# tmux status bar
set -g status-right '#(aiquota --compact)'
```

`--json` gives you `{generated_at, services: [{name, service, plan, tier,
windows: [{label, used_pct, resets_at}], extra}]}`.

## Desktop widgets

Keep it on screen instead of typing a command:

- **Menu bar** (SwiftBar/xbar) — `AI 46%` at the top of the screen, over every app
- **Desktop** (Übersicht) — a panel drawn on the wallpaper

Both live in [`widgets/`](widgets/) with install steps.

## Development

```bash
python3 -m unittest discover -s tests -v    # 31 tests, no network, ~0.2s
```

Tests set `AIQUOTA_NO_AUTODISCOVER=1` so they never pick up real credentials.

## License

MIT
