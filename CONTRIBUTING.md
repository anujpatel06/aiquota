# Contributing

Thanks for helping out. The most useful contribution is usually **a new adapter**.

## Adding a service

You don't need to fork to try one — drop a `.py` file in
`~/.config/aiquota/adapters/` and it loads automatically. When it works, move it
to `aiquota/adapters/` and open a PR.

See the adapter example in the README. The rules that matter:

1. **Never raise from `probe()`.** Return `tier=ERROR` with a message a human
   can act on. One broken adapter must not break the whole run.
2. **Be honest about `tier`.** `LIVE` means you fetched it from the service.
   `MANUAL` means a human typed it. `LOCAL` means you estimated it from logs.
   Mislabelling this is the one thing that makes the tool worse than useless.
3. **Declare `cost_note`** if probing spends quota or money, and say so in the
   PR. Users deserve to know before they put it on a timer.
4. **Stdlib only.** Use `adapters/_http.py`. No new dependencies.
5. **Document the source.** If it's an undocumented endpoint, say where you
   found it and note that it may break.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

Tests must not touch the network or read real credentials — set
`AIQUOTA_NO_AUTODISCOVER=1` and use a temp `AIQUOTA_HOME` (see `tests/`).
Add a case for any behaviour you change.

## Reporting a broken adapter

These endpoints are undocumented and break without warning. When one does,
open an issue with the output of:

```bash
aiquota doctor
aiquota <service> --json -r
```

Redact tokens before posting.
