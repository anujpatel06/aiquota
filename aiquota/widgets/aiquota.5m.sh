#!/bin/bash
# <bitbar.title>AI Quota</bitbar.title>
# <bitbar.version>v1.0</bitbar.version>
# <bitbar.author>Anuj Patel</bitbar.author>
# <bitbar.author.github>anujpatel06</bitbar.author.github>
# <bitbar.desc>Remaining quota across AI subscriptions, in the menu bar.</bitbar.desc>
# <bitbar.dependencies>python3,aiquota</bitbar.dependencies>
# <bitbar.abouturl>https://github.com/anujpatel06/aiquota</bitbar.abouturl>
#
# Refresh interval lives in the FILENAME: aiquota.5m.sh = every 5 minutes.
# Keep it >= 5m — each refresh spends ~1 Haiku token to read Claude's headers.
#
# Install: copy BOTH this file and aiquota_render.py into your SwiftBar
# plugin folder, then `chmod +x aiquota.5m.sh`.

export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

# Resolve the renderer next to this script, wherever the plugin folder is.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$DIR/aiquota_render.py"
