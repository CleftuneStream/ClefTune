#!/usr/bin/env bash
# Removes ClefTune. Your library, settings and downloads are kept unless you pass --purge.
set -euo pipefail

APP_ID="cleftune"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
PREFIX="$DATA_HOME/$APP_ID"
PURGE=0
[ "${1:-}" = "--purge" ] && PURGE=1

rm -f "$HOME/.local/bin/cleftune" "$DATA_HOME/applications/$APP_ID.desktop"
rm -f "$DATA_HOME/icons/hicolor/scalable/apps/$APP_ID.svg" "$DATA_HOME/icons/hicolor/256x256/apps/$APP_ID.png"
rm -rf "$PREFIX/venv"
command -v update-desktop-database >/dev/null && update-desktop-database -q "$DATA_HOME/applications" || true

if [ "$PURGE" = 1 ]; then
  rm -rf "$PREFIX" "${XDG_CACHE_HOME:-$HOME/.cache}/$APP_ID"
  echo "Removed the app, its library, settings and cache. Downloaded music in ~/Music/ClefTune was kept."
else
  echo "Removed the app. Library and settings remain in $PREFIX (use --purge to delete them)."
fi
