#!/usr/bin/env bash
# ClefTune @VERSION@ installer for Linux.
# Self-contained: no root, no Python or other packages needed. Installs for the current user.
#
#   ./ClefTune-@VERSION@-linux-*.run                      guided install / change / uninstall
#   ./ClefTune-...run --mode window|browser --yes          unattended install
#   ./ClefTune-...run --add-window | --remove-window       change an existing install
#   ./ClefTune-...run --uninstall [--purge]                remove (--purge also deletes your library)
set -euo pipefail

APP_NAME="ClefTune"
APP_ID="cleftune"
VERSION="@VERSION@"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
ROOT="$HOME/.local/lib/$APP_ID"             # program files (your library lives in USER_DATA)
BIN_DIR="$HOME/.local/bin"
APPS_DIR="$DATA_HOME/applications"
ICON_DIR="$DATA_HOME/icons/hicolor"
USER_DATA="$DATA_HOME/cleftune"           # library & settings (kept on uninstall unless --purge)
# safety: removing the program folder must never be able to touch the user's library
[ "$ROOT" != "$USER_DATA" ] || { echo "internal error: program and library folders coincide" >&2; exit 1; }
SELF="$(readlink -f "$0")"
ORIG_ARGS=("$@")

MODE=""; ACTION=""; ASSUME_YES=0; PURGE=0; LAUNCH=1
while [ $# -gt 0 ]; do
  case "$1" in
    --mode) MODE="${2:-}"; shift ;;
    --mode=*) MODE="${1#*=}" ;;
    --add-window) ACTION="add-window" ;;
    --remove-window) ACTION="remove-window" ;;
    --uninstall) ACTION="uninstall" ;;
    --purge) PURGE=1 ;;
    -y|--yes) ASSUME_YES=1 ;;
    --no-launch) LAUNCH=0 ;;
    -h|--help) sed -n '2,9p' "$SELF" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $1 (see --help)" >&2; exit 2 ;;
  esac
  shift
done
case "$MODE" in ""|window|browser) ;; *) echo "--mode must be window or browser" >&2; exit 2 ;; esac

# ------------------------------------------------------------------ dialogs (GUI when available)
UI="terminal"
if [ "$ASSUME_YES" = 0 ]; then
  if [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ] && command -v zenity >/dev/null 2>&1; then UI="zenity"
  elif [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ] && command -v kdialog >/dev/null 2>&1; then UI="kdialog"
  elif [ ! -t 0 ]; then
    # double-clicked without a terminal and no dialog tool: reopen in a terminal window
    for term in x-terminal-emulator gnome-terminal konsole xfce4-terminal kitty alacritty xterm; do
      command -v "$term" >/dev/null 2>&1 || continue
      case "$term" in
        gnome-terminal) exec gnome-terminal -- bash "$SELF" "${ORIG_ARGS[@]}" ;;
        *) exec "$term" -e bash "$SELF" "${ORIG_ARGS[@]}" ;;
      esac
    done
  fi
fi

say()  { [ "$UI" = terminal ] && printf '\033[1;35m==>\033[0m %s\n' "$*" || true; }
info() {
  case "$UI" in
    zenity) zenity --info --title="$APP_NAME" --width=420 --text="$*" 2>/dev/null || true ;;
    kdialog) kdialog --title "$APP_NAME" --msgbox "$*" 2>/dev/null || true ;;
    *) printf '\033[1;32m ok\033[0m %s\n' "$*" ;;
  esac
}
die() {
  case "$UI" in
    zenity) zenity --error --title="$APP_NAME" --width=420 --text="$*" 2>/dev/null || true ;;
    kdialog) kdialog --title "$APP_NAME" --error "$*" 2>/dev/null || true ;;
    *) printf '\033[1;31merror:\033[0m %s\n' "$*" >&2 ;;
  esac
  exit 1
}
confirm() {   # confirm "question" -> 0 = yes
  [ "$ASSUME_YES" = 1 ] && return 0
  case "$UI" in
    zenity) zenity --question --title="$APP_NAME" --width=420 --text="$1" 2>/dev/null ;;
    kdialog) kdialog --title "$APP_NAME" --yesno "$1" 2>/dev/null ;;
    *) local r; read -r -p "$1 [Y/n] " r; [[ ! "$r" =~ ^[nN] ]] ;;
  esac
}
choose() {    # choose "question" key1 "label1" key2 "label2" ... -> prints key (first = default)
  local question="$1"; shift
  local keys=() labels=()
  while [ $# -gt 0 ]; do keys+=("$1"); labels+=("$2"); shift 2; done
  local i
  case "$UI" in
    zenity)
      local rows=() state=TRUE
      for i in "${!keys[@]}"; do rows+=("$state" "${keys[$i]}" "${labels[$i]}"); state=FALSE; done
      zenity --list --radiolist --title="$APP_NAME" --text="$question" --width=560 --height=300 \
        --column="" --column="key" --column="Option" --hide-column=2 --print-column=2 "${rows[@]}" 2>/dev/null ;;
    kdialog)
      local rows=() state=on
      for i in "${!keys[@]}"; do rows+=("${keys[$i]}" "${labels[$i]}" "$state"); state=off; done
      kdialog --title "$APP_NAME" --radiolist "$question" "${rows[@]}" 2>/dev/null ;;
    *)
      echo "$question" >&2
      for i in "${!keys[@]}"; do echo "  $((i + 1))) ${labels[$i]}" >&2; done
      local pick
      read -r -p "Choose [1]: " pick
      pick="${pick:-1}"
      [[ "$pick" =~ ^[0-9]+$ ]] && [ "$pick" -ge 1 ] && [ "$pick" -le "${#keys[@]}" ] || return 1
      echo "${keys[$((pick - 1))]}" ;;
  esac
}
with_progress() {   # with_progress "message" command...
  local message="$1"
  shift
  if [ "$UI" = zenity ]; then
    local status="$TMP/status"
    ( "$@"; echo $? > "$status" ) | zenity --progress --pulsate --auto-close --no-cancel --title="$APP_NAME" \
      --width=420 --text="$message" 2>/dev/null || true
    return "$(cat "$status" 2>/dev/null || echo 1)"
  fi
  say "$message"
  "$@"
}

[ "$(id -u)" = 0 ] && die "Please run the installer as your normal user, not as root. It installs into your home folder."
case "$(uname -m)" in x86_64|amd64|aarch64|arm64) ;; *) die "Unsupported processor: $(uname -m)" ;; esac

# ------------------------------------------------------------------ payload (cleaned up on exit)
TMP="$(mktemp -d "${TMPDIR:-/tmp}/cleftune-installer.XXXXXX")"
cleanup() { rm -rf "$TMP" "$ROOT"/.staging-* 2>/dev/null || true; }
trap cleanup EXIT INT TERM

payload_extract() {   # payload_extract member...
  local line
  line="$(awk '/^__CLEFTUNE_PAYLOAD__$/ { print NR + 1; exit }' "$SELF")"
  tail -n +"$line" "$SELF" | tar -x -C "$TMP" "$@"
}

is_installed() { [ -x "$ROOT/app/ClefTune" ]; }
has_window() { [ -x "$ROOT/window/ClefTuneWindow" ]; }
current_mode() { sed -n 's/.*"ui_mode": *"\([a-z]*\)".*/\1/p' "$ROOT/install.json" 2>/dev/null || true; }

stop_running_app() {
  local pids
  pids="$(pgrep -f "$ROOT/(app|window)/ClefTune" 2>/dev/null || true)"
  [ -z "$pids" ] && return 0
  confirm "$APP_NAME is running. Close it to continue?" || die "Installation cancelled."
  kill -TERM $pids 2>/dev/null || true
  for _ in $(seq 1 20); do pgrep -f "$ROOT/(app|window)/ClefTune" >/dev/null 2>&1 || return 0; sleep 0.25; done
  kill -KILL $pids 2>/dev/null || true
}

install_component() {   # install_component core|window
  local name="$1" dest folder
  if [ "$name" = core ]; then dest="$ROOT/app"; folder="ClefTune"; else dest="$ROOT/window"; folder="ClefTuneWindow"; fi
  payload_extract "$name.tar.xz"
  local staging="$ROOT/.staging-$name"
  rm -rf "$staging"
  mkdir -p "$staging"
  tar -xJf "$TMP/$name.tar.xz" -C "$staging"
  rm -f "$TMP/$name.tar.xz"               # free space as we go
  rm -rf "$dest"
  mv "$staging/$folder" "$dest"
  rm -rf "$staging"
}

write_marker() {   # write_marker MODE
  local window=false
  has_window && window=true
  cat > "$ROOT/install.json" <<EOF
{"version": "$VERSION", "ui_mode": "$1", "window": $window, "stamp": $(date +%s)}
EOF
}

integrate_desktop() {
  payload_extract icon.png
  mkdir -p "$BIN_DIR" "$APPS_DIR" "$ICON_DIR/256x256/apps"
  rm -f "$ICON_DIR/scalable/apps/$APP_ID.svg"     # older versions' icon would shadow the new one
  cp "$TMP/icon.png" "$ICON_DIR/256x256/apps/$APP_ID.png"
  cat > "$BIN_DIR/$APP_ID" <<EOF
#!/bin/sh
exec "$ROOT/app/ClefTune" "\$@"
EOF
  chmod +x "$BIN_DIR/$APP_ID"
  {
    echo "[Desktop Entry]"
    echo "Type=Application"
    echo "Name=$APP_NAME"
    echo "GenericName=Music Player"
    echo "Comment=Unofficial YouTube Music client"
    echo "Exec=\"$ROOT/app/ClefTune\""
    echo "Icon=$APP_ID"
    echo "Terminal=false"
    echo "Categories=AudioVideo;Audio;Music;Player;"
    echo "Keywords=youtube;music;player;lyrics;"
    echo "StartupNotify=false"
    echo "StartupWMClass=$APP_ID"
    if has_window; then
      echo "Actions=browser;window;"
    else
      echo "Actions=browser;"
    fi
    echo
    echo "[Desktop Action browser]"
    echo "Name=Open in web browser"
    echo "Exec=\"$ROOT/app/ClefTune\" --browser"
    if has_window; then
      echo
      echo "[Desktop Action window]"
      echo "Name=Open in its own window"
      echo "Exec=\"$ROOT/app/ClefTune\" --window"
    fi
  } > "$APPS_DIR/$APP_ID.desktop"
  # uninstaller that doesn't need the installer file
  cat > "$ROOT/uninstall.sh" <<EOF
#!/usr/bin/env bash
# Removes $APP_NAME. Add --purge to also delete your library and settings ($USER_DATA).
pkill -TERM -f "$ROOT/(app|window)/ClefTune" 2>/dev/null || true
sleep 1
rm -rf "$ROOT" "$BIN_DIR/$APP_ID" "$APPS_DIR/$APP_ID.desktop" \\
       "$ICON_DIR/scalable/apps/$APP_ID.svg" "$ICON_DIR/256x256/apps/$APP_ID.png"
[ "\${1:-}" = "--purge" ] && rm -rf "$USER_DATA" "\${XDG_CACHE_HOME:-\$HOME/.cache}/cleftune"
command -v update-desktop-database >/dev/null && update-desktop-database -q "$APPS_DIR" || true
echo "$APP_NAME removed."
EOF
  chmod +x "$ROOT/uninstall.sh"
  command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q "$APPS_DIR" || true
  refresh_icon_caches
  rm -f "$TMP/icon.png"
}

refresh_icon_caches() {
  # The icon keeps its name across versions, so desktops keep showing the old picture from their
  # caches unless told otherwise (KDE Plasma especially).
  touch "$ICON_DIR" "$ICON_DIR/256x256/apps" 2>/dev/null || true
  command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q -f -t "$ICON_DIR" 2>/dev/null || true
  rm -f "${XDG_CACHE_HOME:-$HOME/.cache}/icon-cache.kcache"
  for k in kbuildsycoca6 kbuildsycoca5; do
    command -v "$k" >/dev/null 2>&1 && { "$k" --noincremental >/dev/null 2>&1 || true; break; }
  done
  command -v xdg-desktop-menu >/dev/null 2>&1 && xdg-desktop-menu forceupdate 2>/dev/null || true
}

remove_legacy_installs() {
  # ClefTune used to be "Metrolist Desktop": a from-source install (Python venv in ~/.local/share/metrodesk)
  # and/or an installer build (~/.local/share/metrolist-desktop). The library itself moves over on first start.
  local old_data="$DATA_HOME/metrodesk" old_root="$DATA_HOME/metrolist-desktop"
  [ -d "$old_data/venv" ] || [ -d "$old_root" ] || return 0
  confirm "An older version (Metrolist Desktop) is installed. Remove it? Your library and settings move to $APP_NAME." || return 0
  pkill -TERM -f "$old_root/(app|window)/|$old_data/venv/bin/" 2>/dev/null || true
  sleep 1
  rm -rf "$old_data/venv" "$old_root" "$BIN_DIR/metrodesk" "$BIN_DIR/metrolist-desktop" \
         "$APPS_DIR/metrodesk.desktop" "$APPS_DIR/metrolist-desktop.desktop" \
         "$ICON_DIR/scalable/apps/metrodesk.svg" "$ICON_DIR/256x256/apps/metrodesk.png" \
         "$ICON_DIR/256x256/apps/metrolist-desktop.png"
}

do_uninstall() {
  is_installed || [ -d "$ROOT" ] || die "$APP_NAME is not installed."
  if [ "$PURGE" = 0 ] && [ "$ASSUME_YES" = 0 ]; then
    confirm "Also delete your library, playlists and settings?" && PURGE=1
  fi
  stop_running_app
  bash "$ROOT/uninstall.sh" $([ "$PURGE" = 1 ] && echo --purge) >/dev/null 2>&1 || rm -rf "$ROOT"
  info "$APP_NAME was removed.$([ "$PURGE" = 1 ] || echo " Your library is kept in $USER_DATA.")"
}

launch_app() {
  [ "$LAUNCH" = 1 ] || return 0
  [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ] || return 0
  confirm "Start $APP_NAME now?" || return 0
  (setsid "$ROOT/app/ClefTune" >/dev/null 2>&1 < /dev/null &) || true
}

# ------------------------------------------------------------------ main flow
if [ "$ACTION" = uninstall ]; then do_uninstall; exit 0; fi

if [ -z "$ACTION" ] && is_installed && [ "$ASSUME_YES" = 0 ]; then
  if has_window; then
    window_option=(remove-window "Remove the separate window (open in my web browser)")
  else
    window_option=(add-window "Add the separate window")
  fi
  ACTION="$(choose "$APP_NAME is already installed. What would you like to do?" \
    update "Install version $VERSION (keeps your choices and library)" \
    "${window_option[@]}" \
    uninstall "Uninstall" )" || exit 0
  [ -n "$ACTION" ] || exit 0
  if [ "$ACTION" = uninstall ]; then do_uninstall; exit 0; fi
fi

case "$ACTION" in
  add-window)
    is_installed || die "Install $APP_NAME first (run this file without options)."
    stop_running_app
    with_progress "Adding the separate window…" install_component window || die "Couldn't add the window."
    write_marker window
    integrate_desktop
    info "The separate window is installed. $APP_NAME will now open in its own window."
    launch_app
    exit 0 ;;
  remove-window)
    is_installed || die "$APP_NAME is not installed."
    stop_running_app
    rm -rf "$ROOT/window"
    write_marker browser
    integrate_desktop
    info "Removed the separate window. $APP_NAME will open in your web browser."
    exit 0 ;;
  update)
    MODE="${MODE:-$(current_mode)}"
    [ -n "$MODE" ] || { has_window && MODE=window || MODE=browser; } ;;
esac

if [ -z "$MODE" ]; then
  if [ "$ASSUME_YES" = 1 ]; then
    MODE=window
  else
    MODE="$(choose "How would you like $APP_NAME to open?

You can change this later in Settings, or by running this installer again." \
      window "In its own window (recommended)" \
      browser "In my web browser (smaller install; audio plays in a browser tab)")" || exit 0
    [ -n "$MODE" ] || exit 0
  fi
fi

stop_running_app
mkdir -p "$ROOT"
with_progress "Installing $APP_NAME $VERSION…" install_component core || die "Installation failed."
if [ "$MODE" = window ]; then
  with_progress "Installing the separate window…" install_component window || die "Installing the window failed."
else
  rm -rf "$ROOT/window"
fi
write_marker "$MODE"
integrate_desktop
remove_legacy_installs

case ":$PATH:" in
  *":$BIN_DIR:"*) cmd_hint="the command $APP_ID" ;;
  *) cmd_hint="$BIN_DIR/$APP_ID" ;;
esac
info "$APP_NAME $VERSION is installed.

Start it from your applications menu or with $cmd_hint.
Opens in: $([ "$MODE" = window ] && echo "its own window" || echo "your web browser")"
launch_app
exit 0
