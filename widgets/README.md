# Desktop widgets

Two ways to keep `aiquota` on screen. Both call the same CLI, so whatever
services you've configured show up automatically.

Install the CLI first:

```bash
uv tool install aiquota     # or: pipx install aiquota
aiquota                     # confirm it works
```

---

## Menu bar — SwiftBar

Always visible, over every app. This is the one most people want.

```bash
brew install --cask swiftbar
mkdir -p ~/.local/share/swiftbar
cp swiftbar/aiquota.5m.sh swiftbar/aiquota_render.py ~/.local/share/swiftbar/
chmod +x ~/.local/share/swiftbar/aiquota.5m.sh
open /Applications/SwiftBar.app
```

On first launch SwiftBar asks for a plugin folder — pick
`~/.local/share/swiftbar`. You'll get `AI 46%` in the menu bar (the
highest window across all services), and clicking it drops down the full
breakdown with reset times.

Both files must sit in the same folder; the `.sh` finds the renderer beside
itself. It also works in [xbar](https://xbarapp.com/) unchanged.

**Change the refresh rate by renaming the file** — `aiquota.5m.sh` is every
5 minutes, `aiquota.15m.sh` every 15. Don't go below 5m: each refresh spends
about one Haiku token reading Claude's rate-limit headers.

## Desktop — Übersicht

Draws on the wallpaper itself, behind your windows.

```bash
brew install --cask ubersicht
cp ubersicht/aiquota.jsx ~/Library/Application\ Support/Übersicht/widgets/
open /Applications/Übersicht.app
```

Übersicht needs **Screen Recording** permission (System Settings → Privacy &
Security → Screen Recording) to draw on the desktop. It prompts on first
launch; if you dismissed it, enable it manually and restart.

Edit `className` at the top of the `.jsx` to move it — `top`/`right` are
plain CSS. The widget re-renders on save, so you can nudge it live.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Menu bar shows `AI ⚠` | `aiquota` isn't on SwiftBar's PATH. Check `which aiquota`; if it's somewhere unusual, add that dir to the `export PATH=` line in the `.sh`. |
| Menu bar item missing entirely | Plugin folder isn't set. SwiftBar → Preferences → Plugin Folder. |
| Desktop widget invisible | Grant Screen Recording permission, then restart Übersicht. |
| Numbers never change | Both widgets pass `--ttl 240` so they share one probe. Run `aiquota -r` to force a refresh and confirm the CLI itself updates. |
