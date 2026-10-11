#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BINARY="$SCRIPT_DIR/beacon"
if [[ ! -f "$BINARY" ]]; then
  echo "ERROR: beacon executable missing. Extract the full release archive." >&2
  exit 1
fi
INSTALL_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}"
BIN_DIR="$HOME/.local/bin"
APP_DIR="$INSTALL_ROOT/applications"
ICON_DIR="$INSTALL_ROOT/icons/hicolor/scalable/apps"
mkdir -p "$BIN_DIR" "$APP_DIR" "$ICON_DIR"
install -m 0755 "$BINARY" "$BIN_DIR/beacon"
# Desktop launchers cannot assume ~/.local/bin is on a graphical session PATH.
sed "s|^Exec=beacon$|Exec=$BIN_DIR/beacon|" "$SCRIPT_DIR/beacon.desktop" > "$APP_DIR/beacon.desktop"
chmod 0644 "$APP_DIR/beacon.desktop"
install -m 0644 "$SCRIPT_DIR/beacon.svg" "$ICON_DIR/beacon.svg"
echo "Installed Beacon: $BIN_DIR/beacon"
