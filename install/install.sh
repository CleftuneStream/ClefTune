#!/usr/bin/env bash
# ClefTune installer for Linux.
# Installs per-user into ~/.local (no root), optionally installing system packages with sudo.
#
#   ./install/install.sh            interactive
#   ./install/install.sh --yes      don't ask, install system packages too
#   ./install/install.sh --no-deps  skip system packages (you install them yourself)
set -euo pipefail

APP_ID="cleftune"
APP_NAME="ClefTune"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
PREFIX="$DATA_HOME/$APP_ID"
VENV="$PREFIX/venv"
BIN_DIR="$HOME/.local/bin"
APPS_DIR="$DATA_HOME/applications"
ICON_DIR="$DATA_HOME/icons/hicolor"

ASSUME_YES=0
SKIP_DEPS=0
for arg in "$@"; do
  case "$arg" in
    -y|--yes) ASSUME_YES=1 ;;
    --no-deps) SKIP_DEPS=1 ;;
    -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

say()  { printf '\033[1;35m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m ok\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m !!\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; exit 1; }
ask()  { [ "$ASSUME_YES" = 1 ] && return 0; read -r -p "$1 [Y/n] " r; [[ ! "$r" =~ ^[nN] ]]; }

[ "$(id -u)" = 0 ] && die "Run this as your normal user, not root (sudo is used only for system packages)."

# ---------------------------------------------------------------- system packages
install_system_packages() {
  local pm="" required=() optional=()
  if command -v apt-get >/dev/null; then
    pm="apt"
    local mpv="libmpv2"; apt-cache show libmpv2 >/dev/null 2>&1 || mpv="libmpv1"
    local webkit="gir1.2-webkit2-4.1"; apt-cache show "$webkit" >/dev/null 2>&1 || webkit="gir1.2-webkit2-4.0"
    required=(python3 python3-venv python3-pip python3-gi "$webkit" "$mpv")
    optional=(gstreamer1.0-plugins-good gstreamer1.0-libav ffmpeg)
  elif command -v dnf >/dev/null; then
    pm="dnf"
    required=(python3 python3-pip python3-gobject webkit2gtk4.1 mpv-libs)
    optional=(gstreamer1-plugins-good ffmpeg-free)
  elif command -v pacman >/dev/null; then
    pm="pacman"
    required=(python python-pip python-gobject webkit2gtk-4.1 mpv)
    optional=(gst-plugins-good gst-libav ffmpeg)
  elif command -v zypper >/dev/null; then
    pm="zypper"
    required=(python3 python3-pip python3-gobject typelib-1_0-WebKit2-4_1 libmpv2)
    optional=(gstreamer-plugins-good ffmpeg)
  else
    warn "Unknown package manager. Please install yourself: Python 3.10+ with venv, PyGObject, WebKit2GTK 4.1, libmpv, ffmpeg."
    return
  fi

  say "System packages ($pm): ${required[*]} (+ optional: ${optional[*]})"
  ask "Install them now with sudo?" || { warn "Skipped. The app falls back to your browser if WebKit2GTK is missing, and to built-in audio if libmpv is missing."; return; }

  local run=(sudo)
  case "$pm" in
    apt)    sudo apt-get update -q; run+=(apt-get install -y) ;;
    dnf)    run+=(dnf install -y) ;;
    pacman) run+=(pacman -S --needed --noconfirm) ;;
    zypper) run+=(zypper --non-interactive install) ;;
  esac
  if ! "${run[@]}" "${required[@]}"; then
    warn "Bulk install failed; trying packages one by one."
    for p in "${required[@]}"; do "${run[@]}" "$p" || warn "could not install $p"; done
  fi
  for p in "${optional[@]}"; do "${run[@]}" "$p" >/dev/null 2>&1 && ok "$p" || warn "optional package $p not installed"; done
}

[ "$SKIP_DEPS" = 1 ] || install_system_packages

# ---------------------------------------------------------------- python
PY="$(command -v python3 || true)"
[ -n "$PY" ] || die "python3 not found."
"$PY" -c 'import sys; sys.exit(sys.version_info < (3, 10))' || die "Python 3.10 or newer is required (found $("$PY" -V))."
ok "$("$PY" -V)"

say "Creating virtual environment in $VENV"
mkdir -p "$PREFIX"
# --system-site-packages exposes the distro's PyGObject (gi), which pip can't build easily
"$PY" -m venv --clear --system-site-packages "$VENV" || die "venv failed. On Debian/Ubuntu install python3-venv."
"$VENV/bin/python" -m pip install --quiet --upgrade pip wheel

TARGET="$SRC_DIR"
if command -v deno >/dev/null || command -v node >/dev/null || command -v bun >/dev/null; then
  ok "JavaScript runtime found ($(command -v deno || command -v node || command -v bun)); not bundling Deno"
else
  say "No Deno/Node/Bun found: bundling Deno for yt-dlp (~90 MB)"
  TARGET="$SRC_DIR[deno]"
fi
say "Installing $APP_NAME and its Python dependencies"
"$VENV/bin/python" -m pip install --quiet --upgrade "$TARGET"

# ---------------------------------------------------------------- launcher, menu entry, icons
mkdir -p "$BIN_DIR" "$APPS_DIR" "$ICON_DIR/scalable/apps" "$ICON_DIR/256x256/apps"
ln -sf "$VENV/bin/cleftune" "$BIN_DIR/cleftune"
WEB="$("$VENV/bin/python" -c 'import cleftune, os; print(os.path.join(os.path.dirname(cleftune.__file__), "web"))')"
rm -f "$ICON_DIR/scalable/apps/$APP_ID.svg"     # older versions' icon would shadow the new one
cp "$WEB/icon.png" "$ICON_DIR/256x256/apps/$APP_ID.png"
cat > "$APPS_DIR/$APP_ID.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=$APP_NAME
GenericName=Music Player
Comment=Unofficial YouTube Music client
Exec="$VENV/bin/cleftune"
Icon=$APP_ID
Terminal=false
Categories=AudioVideo;Audio;Music;Player;
Keywords=youtube;music;player;lyrics;
StartupNotify=true
EOF
command -v update-desktop-database >/dev/null && update-desktop-database -q "$APPS_DIR" || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q -t "$ICON_DIR" 2>/dev/null || true
ok "Menu entry and 'cleftune' command installed"

# ---------------------------------------------------------------- report
say "Checking components"
if "$VENV/bin/python" -c 'import mpv' 2>/dev/null; then ok "libmpv: native audio engine"; else warn "libmpv not found: using built-in audio (install libmpv for lower memory use)"; fi
if "$VENV/bin/python" - <<'PY' 2>/dev/null
import gi
for v in ("4.1", "4.0"):
    try:
        gi.require_version("WebKit2", v); break
    except ValueError:
        continue
else:
    raise SystemExit(1)
from gi.repository import WebKit2  # noqa
PY
then ok "WebKit2GTK: native window"; else warn "WebKit2GTK/PyGObject not found: the app opens in your web browser instead"; fi
command -v ffmpeg >/dev/null && ok "ffmpeg: downloads get tags and cover art" || warn "ffmpeg not found: downloads work but stay untagged"
case ":$PATH:" in *":$BIN_DIR:"*) ;; *) warn "$BIN_DIR is not on your PATH; start from the app menu or run $BIN_DIR/cleftune" ;; esac

echo
ok "$APP_NAME installed. Launch it from your app menu or run: cleftune"
