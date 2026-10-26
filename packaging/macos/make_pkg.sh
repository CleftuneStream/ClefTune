#!/usr/bin/env bash
# Assemble the macOS installer package.
#   make_pkg.sh CORE_APP WINDOW_APP OUT_PKG VERSION ARCH
# Optional signing: MACOS_INSTALLER_IDENTITY="Developer ID Installer: ..." (then notarize the .pkg).
set -euo pipefail
CORE_APP="$1"; WINDOW_APP="$2"; OUT="$3"; VERSION="$4"; ARCH="$5"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ID="io.github.cleftune"
SUPPORT="/Library/Application Support/ClefTune"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/core-root" "$work/window-root" "$work/core-scripts" "$work/window-scripts" "$work/resources"
ditto "$CORE_APP" "$work/core-root/ClefTune.app"
ditto "$WINDOW_APP" "$work/window-root/ClefTune Window.app"

# --- install scripts: record the choice; the app applies it once per installer run (stamp)
cat > "$work/core-scripts/postinstall" <<EOF
#!/bin/sh
mkdir -p "$SUPPORT"
# the window package (if ticked) installs right after this one; drop any old copy first
rm -rf "$SUPPORT/ClefTune Window.app"
printf '{"version": "$VERSION", "ui_mode": "browser", "window": false, "stamp": %s}\n' "\$(date +%s)" > "$SUPPORT/install.json"
cat > "$SUPPORT/Uninstall ClefTune.command" <<'UNINSTALL'
#!/bin/sh
echo "Removing ClefTune (your password is needed)…"
pkill -f "ClefTune.app/Contents/MacOS/ClefTune" 2>/dev/null
sudo rm -rf "/Applications/ClefTune.app" "$SUPPORT"
sudo pkgutil --forget $ID.app >/dev/null 2>&1
sudo pkgutil --forget $ID.window >/dev/null 2>&1
echo "Done. Your library is kept in ~/Library/Application Support/ClefTune."
UNINSTALL
chmod 755 "$SUPPORT/Uninstall ClefTune.command"
chmod 644 "$SUPPORT/install.json"
exit 0
EOF
cat > "$work/window-scripts/postinstall" <<EOF
#!/bin/sh
printf '{"version": "$VERSION", "ui_mode": "window", "window": true, "stamp": %s}\n' "\$(date +%s)" > "$SUPPORT/install.json"
chmod 644 "$SUPPORT/install.json"
exit 0
EOF
chmod 755 "$work/core-scripts/postinstall" "$work/window-scripts/postinstall"

# --- component packages (bundles must not be "relocated" to another copy on disk)
for part in core window; do
  pkgbuild --analyze --root "$work/$part-root" "$work/$part.plist"
  plutil -replace 0.BundleIsRelocatable -bool NO "$work/$part.plist"
done
pkgbuild --root "$work/core-root" --component-plist "$work/core.plist" --install-location /Applications \
  --scripts "$work/core-scripts" --identifier "$ID.app" --version "$VERSION" "$work/core.pkg"
pkgbuild --root "$work/window-root" --component-plist "$work/window.plist" --install-location "$SUPPORT" \
  --scripts "$work/window-scripts" --identifier "$ID.window" --version "$VERSION" "$work/window.pkg"

cp "$HERE/welcome.html" "$work/resources/welcome.html"
host_arch="$([ "$ARCH" = arm64 ] && echo arm64 || echo x86_64)"
cat > "$work/distribution.xml" <<EOF
<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="2">
  <title>ClefTune $VERSION</title>
  <welcome file="welcome.html" mime-type="text/html"/>
  <options customize="always" require-scripts="false" hostArchitectures="$host_arch"/>
  <domains enable_localSystem="true"/>
  <volume-check><allowed-os-versions><os-version min="11.0"/></allowed-os-versions></volume-check>
  <choices-outline>
    <line choice="core"/>
    <line choice="window"/>
  </choices-outline>
  <choice id="core" title="ClefTune" enabled="false" selected="true"
          description="The music player. On its own it opens in your web browser.">
    <pkg-ref id="$ID.app"/>
  </choice>
  <choice id="window" title="Separate window (recommended)" start_selected="true"
          description="Show ClefTune in its own window instead of a browser tab. Untick to use your web browser. You can add it later by opening this installer again.">
    <pkg-ref id="$ID.window"/>
  </choice>
  <pkg-ref id="$ID.app" version="$VERSION" onConclusion="none">core.pkg</pkg-ref>
  <pkg-ref id="$ID.window" version="$VERSION" onConclusion="none">window.pkg</pkg-ref>
</installer-gui-script>
EOF

sign=()
[ -n "${MACOS_INSTALLER_IDENTITY:-}" ] && sign=(--sign "$MACOS_INSTALLER_IDENTITY")
# ${arr[@]+...}: macOS ships bash 3.2, where an empty array trips `set -u`
productbuild --distribution "$work/distribution.xml" --resources "$work/resources" --package-path "$work" \
  ${sign[@]+"${sign[@]}"} "$OUT"
echo "Built $OUT"
