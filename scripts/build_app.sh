#!/bin/bash
# Package AIQuotaBar as a real .app bundle.
#
# No Xcode required — swiftpm builds the binary and we assemble the bundle by
# hand, because Xcode is a 15GB dependency for what is fundamentally a
# directory with a plist in it.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/macapp"

VERSION="$(python3 -c "
import re,pathlib
t=(pathlib.Path('$ROOT')/'aiquota/__init__.py').read_text()
print(re.search(r'__version__ = \"([^\"]+)\"',t).group(1))")"

echo "==> building AIQuotaBar $VERSION"
swift build -c release

APP="$ROOT/dist/AIQuotaBar.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp .build/release/AIQuotaBar "$APP/Contents/MacOS/"

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>AIQuotaBar</string>
  <key>CFBundleDisplayName</key><string>AIQuotaBar</string>
  <key>CFBundleIdentifier</key><string>com.anujpatel.aiquotabar</string>
  <key>CFBundleVersion</key><string>$VERSION</string>
  <key>CFBundleShortVersionString</key><string>$VERSION</string>
  <key>CFBundleExecutable</key><string>AIQuotaBar</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <!-- Menu bar only: no Dock icon, no window on launch. -->
  <key>LSUIElement</key><true/>
  <key>NSHumanReadableCopyright</key><string>MIT</string>
</dict>
</plist>
PLIST

# Ad-hoc sign so Gatekeeper treats it as a valid (if unidentified) bundle.
# A Developer ID signature needs a paid Apple account; without one this is
# the honest best, and the README says so rather than pretending otherwise.
codesign --force --deep --sign - "$APP" 2>/dev/null \
  && echo "==> ad-hoc signed" \
  || echo "==> WARNING: could not sign"

echo "==> $APP"
du -sh "$APP" | awk '{print "    size: "$1}'
