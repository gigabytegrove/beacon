#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${XDG_DATA_HOME:-$HOME/.local/share}"
rm -f "$HOME/.local/bin/beacon" "$ROOT/applications/beacon.desktop"
rm -f "$ROOT/icons/hicolor/scalable/apps/beacon.svg"
echo "Uninstalled Beacon executable and desktop entry; user settings were kept."
