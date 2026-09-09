# Vision

aiquota answers one question: **how much of everything I pay for is left?**

Not tokens. Not cost-per-request estimates. The subscription allowances a
person actually buys — Claude Pro, ChatGPT Plus, Cursor, Perplexity, Leonardo,
HeyGen — in one place, without opening six dashboards.

## What makes this different

Every other tool in this space tracks **coding** providers. CodexBar's own
tagline is "every AI *coding* limit". That leaves the designer paying for
Leonardo, the video editor paying for HeyGen, and the researcher paying for
Perplexity with nothing to look at.

aiquota covers both, and it says what it cannot do.

## Rules that don't bend

**Never show a number the provider didn't give us.** No estimates dressed as
readings. If a value is typed by hand it's labelled `manual`; if it came from
the provider it's `live`; if we can't tell how precise it is, `confidence`
says so. Tests enforce this — a manual value cannot render as live.

**Never read a provider that forbids it.** Midjourney, Suno, Udio, Luma,
Descript and Bolt.new all have working endpoints and all prohibit automated
access. Their adapters are deleted, not disabled, and a test fails if anyone
re-adds the endpoints. A quota number is not worth someone's account.

**Never borrow a credential the user didn't offer.** Reading another app's
tokens is opt-in per service. Credentials are never printed, never logged,
never sent anywhere except the provider they belong to.

**Never spend quota to measure quota.** Where a provider offers a read-only
usage endpoint and an inference-based one, the read-only route wins.

**Zero third-party dependencies.** Standard library only. A tool that reads
your credentials should have the smallest possible supply chain.

## Merge by default

- New providers that follow the existing adapter + policy + test pattern
- Bug fixes with a clear cause and a regression test
- Performance work with a before/after measurement
- Documentation corrections
- Widget and CLI polish

## Needs discussion first

- Anything that adds a dependency
- Anything that reads a new credential source or filesystem location
- A provider whose terms are ambiguous about automated access
- Architecture changes, or new surfaces to maintain
- Anything that displays a derived number as if the provider stated it

## Scope

**macOS** is where the UI lives: menu bar and desktop widgets.

**The CLI works anywhere** Python runs. `aiquota status --json` and
`aiquota serve` are the supported integration points — if you want aiquota on
Linux, in tmux, in Raycast or on a Stream Deck, consume those rather than
waiting for us to build it. Good integrations get linked from the README.

## Non-goals

- **Per-request cost accounting.** [ccusage](https://github.com/ccusage/ccusage)
  does this well for Claude Code. We track subscription allowance.
- **Being a proxy or gateway.** aiquota reads; it never sits in the path of
  your actual API calls.
- **Provider count as a scoreboard.** A provider we can read honestly and
  lawfully is worth ten we can't.
