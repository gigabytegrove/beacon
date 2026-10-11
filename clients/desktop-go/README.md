# Beacon Go desktop client — Windows and Linux

This is the **primary desktop client** from v0.8.0 onward. It's written in **Go**, using [Fyne](https://fyne.io/) for native desktop windows. It is **not** a Python/Tkinter application and is not a Python wrapper. The same codebase builds on Windows and Linux; users run a binary produced by the release build.

## End-user installation

**Windows:** Obtain a **verified** `Beacon-Windows-0.8.0.exe` build artifact; place it in a folder and double-click it. No Python, pip, Go SDK, or Fyne installation is required. An unsigned development build may display a Windows SmartScreen reputation warning; do not bypass it without verifying its provenance/hash.

**Linux:** Obtain a **verified** `Beacon-Linux-0.8.0.tar.gz`. Extract it, then run the included `./install.sh` as your own user. The archive includes the compiled `beacon` binary, desktop launcher, SVG icon, and uninstall script. It installs under `~/.local/bin` without root. Linux needs its normal graphics system libraries (X11/OpenGL or corresponding Fyne-supported environment); no Python runtime is used or installed.

**Do not assume installers are available just because their workflows exist.** Check GitHub Actions run success, artifact files, checksums, and installation on each target OS.

## AIM-style features in the Go source

- Compact buddy-list window, photo thumbnails, groups, aliases, online/away/busy, unread counters and sign-on notifications
- Individually opening, independently closable conversation windows; saved one-to-one history; typing indicator
- Send message, search history, mark conversation read, catch up after reconnect
- Add/remove/edit buddies, create/rename/delete groups and mute alerts
- Own profile name/status/photo, password rotation, create users (admin), list/revoke device sessions
- Fyne system tray and OS notifications, optional automatic IM pop-out for incoming messages
- Optional **secure** remembered login via the OS credential vault (Windows Credential Manager or Linux Secret Service), never a plaintext `.json` token file

## Developer build (not required for end users)

Go 1.23 or later, Fyne 2.8.1, C compiler and platform graphics development headers. Check the [official Fyne build prerequisites](https://docs.fyne.io/started/quick/).

```bash
cd clients/desktop-go
go mod tidy
go test ./internal/beacon
go build -o beacon ./cmd/beacon
```

On Linux, install your distribution's C compiler, OpenGL/X11 development headers first. Windows builds need MinGW-w64 (configured by CI). Developer build dependencies are used only **to produce** the binary, not when **running** it.

Source layout:

- `cmd/beacon/main.go`: buddy-list windows, secure-login flow, presence, notifications and tray
- `cmd/beacon/dialogs.go`: buddy/group management, profile/photo/password, admin and device sessions
- `cmd/beacon/chat.go`: independent IM windows, typing, search and read synchronization
- `internal/beacon/api.go`: stdlib HTTP client, input validation, bearer session, messages and API contract
- `internal/beacon/api_test.go`: unit/API tests (no GUI or Fyne runtime necessary)

## Operational limits

The Go clients currently use short-interval authenticated HTTP polling for buddies, chat and typing; the browser uses WebSockets. Disconnection during a fetch is handled with a follow-up fetch. Fyne's system tray and notification presentation depend on the desktop environment. On Linux, graphics driver/system libraries may already be present but are not universally guaranteed; Fyne development libraries are **build-time** requirements.

Password/session handling: pressing Logout revokes the current session. Quitting the application from the tray does not automatically log out, allowing optional secure session restoration on reopening. If you prefer to sign out, use **Sign Out**. Without secure credential storage the token stays in process memory and you'll sign in again on next start.

Android remains native Java with a separate client build. The shared server is deployed using [Dokploy Compose](../../docs/DOKPLOY.md).

**Verification status:** Not yet runtime-validated as a packaged Windows/Linux release. Consult [Release Checklist](../../docs/RELEASE-CHECKLIST.md).

## Build locally if GitHub Actions doesn't allocate runners

From a checked-out Beacon repository on a **Windows build workstation** with Go and MinGW-w64 GCC, run `powershell -ExecutionPolicy Bypass -File .\scripts\build-desktop-windows.ps1`. From a **Linux build workstation** with Go/GCC/OpenGL development headers, run `bash scripts/build-desktop-linux.sh`. Outputs and checksums land in `dist/`. The runtime users still need **none** of those developer tools. See [Build and Test](../../docs/BUILD-AND-TEST.md).

## v0.8.0 stabilization

The buddy-list renderer skips expensive UI rebuilds when the roster hasn't changed, keeping the current scroll position. When an account is revoked or a device session expires, the Go desktop clears remembered credentials and returns to the sign-in screen. Both behaviors require platform GUI verification, separate from the Go API tests.
