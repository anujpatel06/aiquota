#!/bin/bash
# Opens the native aiquota platform picker.
# Called by the SwiftBar plugin's "＋ Add an AI account…" item.
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

if command -v aiquota-picker >/dev/null 2>&1; then
  exec aiquota-picker
fi

# Fallback: the picker isn't installed, so use the terminal flow.
osascript \
  -e 'tell application "Terminal" to do script "aiquota link"' \
  -e 'tell application "Terminal" to activate'
