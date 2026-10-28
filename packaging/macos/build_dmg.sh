#!/bin/bash
# Builds dist/VibeSimulation-<version>-macos.dmg on a Mac (Python 3.9+ with Tk, and Xcode command line tools).
# Optional signing + notarization: set SIGN_ID="Developer ID Application: Your Name (TEAMID)" and NOTARY_PROFILE="profile-name"
# (created once with: xcrun notarytool store-credentials profile-name --apple-id you@example.com --team-id TEAMID).
set -e
cd "$(dirname "$0")/../.."
python3 packaging/build.py
VER=$(python3 -c "import sys; sys.path.insert(0,'src'); import vibesimulation; print(vibesimulation.__version__)")
APP="dist/VibeSimulation.app"; DMG="dist/VibeSimulation-$VER-macos.dmg"
if [ -n "$SIGN_ID" ]; then
  codesign --force --deep --options runtime --timestamp --entitlements packaging/macos/entitlements.plist --sign "$SIGN_ID" "$APP"
  codesign --verify --deep --strict --verbose=2 "$APP"
fi
STAGE=$(mktemp -d); cp -R "$APP" "$STAGE/"; ln -s /Applications "$STAGE/Applications"
rm -f "$DMG"; hdiutil create -volname "VibeSimulation $VER" -srcfolder "$STAGE" -ov -format UDZO "$DMG"
if [ -n "$SIGN_ID" ]; then codesign --force --timestamp --sign "$SIGN_ID" "$DMG"; fi
if [ -n "$SIGN_ID" ] && [ -n "$NOTARY_PROFILE" ]; then
  xcrun notarytool submit "$DMG" --keychain-profile "$NOTARY_PROFILE" --wait
  xcrun stapler staple "$DMG"
fi
echo "Built $DMG"
