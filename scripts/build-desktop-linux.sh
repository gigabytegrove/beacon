#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODULE="$ROOT/clients/desktop-go"
DIST="$ROOT/dist"
VERSION="0.8.0"
echo "===== BEACON GO LINUX BUILD ====="
for bin in go gcc pkg-config tar; do
  command -v "$bin" >/dev/null || { echo "Missing $bin on the build computer" >&2; exit 1; }
done
[[ -f "$MODULE/go.mod" ]] || { echo "Missing Go module at $MODULE" >&2; exit 1; }
if ! pkg-config --exists gl x11 xcursor xrandr xi xxf86vm; then
  echo "Missing GUI development headers. On Debian/Ubuntu: apt install libgl1-mesa-dev xorg-dev libxkbcommon-dev" >&2
  exit 1
fi
mkdir -p "$DIST"
cd "$MODULE"
go version
go mod tidy
go test ./internal/beacon
CGO_ENABLED=1 GOOS=linux GOARCH=amd64 go build -trimpath -ldflags="-s -w" -o "$DIST/beacon" ./cmd/beacon
test -s "$DIST/beacon"
TARGET="$DIST/Beacon-Linux-$VERSION"
mkdir -p "$TARGET"
install -m 0755 "$DIST/beacon" "$TARGET/beacon"
for f in beacon.desktop beacon.svg install.sh uninstall.sh; do
  install -m 0644 "$ROOT/clients/desktop/linux/$f" "$TARGET/$f"
done
chmod 0755 "$TARGET/install.sh" "$TARGET/uninstall.sh"
bash -n "$TARGET/install.sh"
bash -n "$TARGET/uninstall.sh"
tar -C "$DIST" -czf "$DIST/Beacon-Linux-$VERSION.tar.gz" "Beacon-Linux-$VERSION"
sha256sum "$DIST/Beacon-Linux-$VERSION.tar.gz" > "$DIST/Beacon-Linux-$VERSION.sha256"
echo "SUCCESS: $DIST/Beacon-Linux-$VERSION.tar.gz"
echo "End users do not need Python, Go SDK, or build tools."
