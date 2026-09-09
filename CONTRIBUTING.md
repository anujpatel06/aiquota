# Contributing

Read [VISION.md](VISION.md) first — it says what gets merged by default and
what needs discussion. The honesty rules there are not style preferences;
tests enforce them.

## Setup

```bash
git clone https://github.com/anujpatel06/aiquota
cd aiquota
python3 -m unittest discover -s tests    # ~1s, no network, no credentials
```

No install step, no virtualenv needed to run tests, no dependencies to fetch.
That's deliberate.

## Adding a provider

1. **Read their terms first.** Search for "automated", "scraping", "robots",
   "data mining". If automated access is prohibited, the provider goes in the
   catalog as `manual` with the clause quoted in `login_policy.py` — and no
   adapter. This has already applied to six providers; it is not hypothetical.

2. **Probe the endpoint unauthenticated** and record what you get:

   ```bash
   curl -s -o /dev/null -w "%{http_code}" https://api.example.com/v1/usage
   ```

   `401`/`403` with a JSON body means the route exists. `404` means you
   guessed. Put the observed status and date in the adapter docstring.

3. **Write the adapter.** Simplest case is a documented key-authenticated
   balance — subclass `KeyBalanceAdapter` in `adapters/key_balance.py` and
   implement `parse()`.

4. **Add** a `catalog.py` entry, a `login_policy.py` entry with a citation
   URL, and tests.

5. **Regenerate docs:** `python3 scripts/gen_platform_table.py`. The README
   table is generated so it cannot claim support that doesn't exist.

## The rules tests enforce

- A `manual` value can never render as `live`
- Prohibited providers have no adapter and no endpoint URLs anywhere
- No hard-coded plan tables to estimate "messages left" — if the provider
  doesn't report it, we don't show it
- `Result.from_dict` tolerates caches written by older versions
- The packaged widget matches the repo widget

If your change makes one of these fail, the test is probably right.

## Before opening a PR

```bash
python3 -m unittest discover -s tests
bash scripts/verify_release.sh     # 9 checks incl. packaging and JSX
```

Performance claims need a before/after measurement in the PR description.
"7.8× with 8 providers at 0.4s each" is useful; "faster" isn't.

## Consuming aiquota from another tool

Don't fork it for this — there are two supported interfaces:

```bash
aiquota status --json      # one-shot
aiquota serve              # localhost HTTP, read-only
```

Build your Raycast extension, tmux segment or Stream Deck plugin on those and
we'll link it from the README.
