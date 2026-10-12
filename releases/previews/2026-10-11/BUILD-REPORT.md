# Beacon Premium desktop build verification

Build date: 2026-10-11. Both clients use the same Go module under `clients/desktop-native-preview`, with native Windows Win32 and Linux X11 GUI entry points.

## Verified

- Go tests: `go test -race -count=1 ./...` passed locally for both the GUI/controller package and its HTTP API package.
- `go vet ./...` passed locally.
- Linux x64 GUI compiled and launched under Xvfb; login, buddy list, independent IM window and message sending exercised against a local simulated API.
- Windows x64 GUI cross-compiled; PE32+ x64 format verified and SHA256 recorded.

## Not verified

- The EXE has not run on a real Windows PC.
- The Linux executable has not been tested on the user's own desktop or a live Dokploy server.
- The full Fyne feature set is **not** present in this native preview.
- Android resource kit is unintegrated and **no Android APK has been built**.

The entire snapshot is intended for UI validation and integration, not a production release.
