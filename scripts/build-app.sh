#!/bin/bash
# Build the double-click launcher: one "Session Doctor.app" menu-bar app.
# Source of truth is scripts/SessionDoctorBar.swift (committed); the .app
# bundle is generated (git-ignored) — run this once per machine/checkout.
# Usage: scripts/build-app.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PROJECT_DIR="$PWD"

command -v swiftc >/dev/null || { echo "swiftc not found — install Xcode Command Line Tools, then retry" >&2; exit 1; }

APP="Session Doctor.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

# Bake the project path in so the app works from anywhere (with a
# sibling-folder fallback if the whole directory moves with the app).
sed "s|%%PROJECT_DIR%%|$PROJECT_DIR|g" scripts/SessionDoctorBar.swift > /tmp/sd-bar-build.swift
swiftc -O -o "$APP/Contents/MacOS/SessionDoctor" /tmp/sd-bar-build.swift -framework AppKit
rm -f /tmp/sd-bar-build.swift

cat > "$APP/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>CFBundleExecutable</key>
	<string>SessionDoctor</string>
	<key>CFBundleIdentifier</key>
	<string>doctor.session.local</string>
	<key>CFBundleName</key>
	<string>Session Doctor</string>
	<key>CFBundleIconFile</key>
	<string>SessionDoctor</string>
	<key>LSUIElement</key>
	<true/>
	<key>NSHighResolutionCapable</key>
	<true/>
	<key>LSMinimumSystemVersion</key>
	<string>13.0</string>
</dict>
</plist>
EOF

# Custom icon: emerald pulse on near-black (matches the web favicon).
if /usr/bin/python3 -c "import PIL" 2>/dev/null && command -v iconutil >/dev/null; then
  ICONSET="$(mktemp -d ./iconset.XXXXXX)/SessionDoctor.iconset"
  mkdir -p "$ICONSET"
  /usr/bin/python3 scripts/make-icon.py "$ICONSET/icon_512x512@2x.png"
  /usr/bin/python3 - "$ICONSET" <<'EOF'
import sys
from PIL import Image
d = sys.argv[1]
img = Image.open(f"{d}/icon_512x512@2x.png")
for s in (16, 32, 128, 256, 512):
    img.resize((s, s), Image.LANCZOS).save(f"{d}/icon_{s}x{s}.png")
    img.resize((s * 2, s * 2), Image.LANCZOS).save(f"{d}/icon_{s}x{s}@2x.png")
EOF
  iconutil -c icns "$ICONSET" -o ./sd-icon.icns
  rm -rf "$(dirname "$ICONSET")"
  cp ./sd-icon.icns "$APP/Contents/Resources/SessionDoctor.icns"
  touch "$APP"
  rm -f ./sd-icon.icns
  echo "icon applied"
else
  echo "PIL/iconutil missing — keeping default icon" >&2
fi

chmod +x scripts/doctor.sh scripts/build-app.sh
plutil -lint "$APP/Contents/Info.plist"
echo "Built: $PWD/$APP"
echo "First launch: right-click the app → Open (unsigned, one time only)."
