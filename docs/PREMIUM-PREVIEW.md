# Beacon premium desktop visual preview — 2026-10-11

## Purpose and boundaries

The repository contains two distinct desktop development lines:

1. **Primary application:** `clients/desktop-go` — the shared Go/Fyne Windows/Linux client with session vault, buddy groups, profile management, tray, notifications, typed status, message history and multi-device synchronization. This remains the supported feature-development baseline.
2. **Native premium visual preview:** `clients/desktop-native-preview` — a separate Go/Win32 + Go/X11 implementation demonstrating the new Beacon login, compact buddy list, directory, chat bubbles, presence badges, empty states, focus/hover behavior, and branding. The premium preview is a **functional subset**, not a drop-in feature-complete replacement.

**Do not remove Fyne capabilities merely because the preview currently looks better.** Integrate the approved visual system into the primary clients without sacrificing functionality, then retire the experimental preview only when explicitly approved.

## Visual system

Use the supplied **Beacon Messenger** branding: bright blue chat bubble with three white dots and wireless signal arcs, navy wordmark, crisp white background. UI palette: navy `#09172D`, ink `#11223F`, primary blue `#1479F7`, sky `#17B2FA`, canvas `#F3F6FC`, panels `#FFFFFF`, subtle labels `#687C96`, online `#15B985`. The UI is flat and accessible. No gradients, fake 3D or unexplained developer controls.

The preview's source contains native window handlers, rasterized visual assets, image/font atlases and screenshots. Actual logos/icons and resources should remain included in the preview source for reproducibility, without shipping font files.

## Actual local verification performed

- Linux x64 binary compiled with Go 1.23 and native X11 linkage.
- Linux GUI launched under Xvfb and exercised sign-in, roster display, independent chat window, and message send against a simulated Beacon HTTP API.
- Windows x64 EXE compiled with Go's Windows Win32 system calls; PE32+ format verified, but **not run on a Windows device**.
- The separate Go preview passed `go test -race -count=1 ./...` and `go vet ./...`.
- Android design kit resources were validated as XML but **were not integrated into the native Java Activity or compiled as an APK**.

**Do not equate simulated API smoke checks with testing against a real Dokploy server.** Do not equate a compiled EXE with successfully executing it on Windows. Do not equate Android XML resources with an installable APK.

## Source layout

`clients/desktop-native-preview/cmd/beacon/` contains cross-platform Go controller/rendering code and native `gui_windows.go`/`gui_linux.go` window implementations. Its resources live in `assets/`. `design/android-premium/` contains Android layouts, colors and drawables as a **design kit**, separate from the current Android project's compiled Java resources.

The preview is intentionally kept outside the primary `clients/desktop-go` Go module and its CI workflow to preserve the existing feature set. No Python interpreter is required by either compiled desktop preview executable.

## Upcoming parity requirements

- Adopt the premium layout across the primary Go/Fyne Windows/Linux login, roster, chat and settings screens.
- Preserve OS credential vault storage, buddy grouping, nickname/mute settings, user presence, read state, multi-window chats and notifications.
- Integrate Android layouts into the Java client with working data binding, accessibility, navigation and correct runtime APIs; build and install a genuine APK.
- Validate real devices and a real Dokploy server. Test Windows sign-in, Bluetooth/hearing accessibility where appropriate, Linux desktop compatibility, Android notifications, and loss/recovery of LAN.
- Publish signed or otherwise verifiably checksummed releases only after full compilation and runtime acceptance.

See [Release Checklist](RELEASE-CHECKLIST.md) for the formal gate.
