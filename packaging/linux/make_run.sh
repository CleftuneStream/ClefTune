#!/usr/bin/env bash
# Assemble the self-extracting Linux installer.
#   make_run.sh CORE_DIR WINDOW_DIR OUT_FILE VERSION WEB_DIR
set -euo pipefail
CORE="$1"; WINDOW="$2"; OUT="$3"; VERSION="$4"; WEB="$5"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

# Separate archives so a browser-only install never unpacks the (large) window add-on.
# The BCJ filter makes machine code compress better and the big dictionary finds repeats across
# libraries: ~10% smaller than plain -9 (decompressing needs ~200 MB of RAM).
case "$(uname -m)" in
  x86_64|amd64) bcj="--x86" ;;
  aarch64|arm64) xz --help 2>/dev/null | grep -q -- "--arm64" && bcj="--arm64" || bcj="" ;;
  *) bcj="" ;;
esac
export XZ_OPT="-T0 $bcj --lzma2=preset=9e,dict=192MiB"
tar -C "$(dirname "$CORE")" -cJf "$work/core.tar.xz" "$(basename "$CORE")"
tar -C "$(dirname "$WINDOW")" -cJf "$work/window.tar.xz" "$(basename "$WINDOW")"
cp "$WEB/icon.png" "$work/"

sed "s/@VERSION@/$VERSION/g" "$HERE/installer.sh" > "$OUT"
printf '%s\n' "__CLEFTUNE_PAYLOAD__" >> "$OUT"
tar -C "$work" -cf - core.tar.xz window.tar.xz icon.png >> "$OUT"
chmod +x "$OUT"
echo "core: $(du -h "$work/core.tar.xz" | cut -f1), window add-on: $(du -h "$work/window.tar.xz" | cut -f1)"
