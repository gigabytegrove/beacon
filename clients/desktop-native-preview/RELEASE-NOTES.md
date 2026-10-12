# Beacon Messenger — Premium Native Desktop Test Build

**Build date:** 2026-10-11 · Go / Win32 Windows x64 · Go / X11 Linux x64

## Substantial user-interface changes

- Replaced all four screen backgrounds with a new premium navy/blue brand system,
  Inter-based high-resolution raster typography, elevated white surfaces,
  generous spacing, and unified connection/status language.
- Stronger login hero, structured form and focus ring, inline friendly network
  error handling, clear primary action and no localhost hard-coded default.
- Rebuilt AIM buddy list: personal profile, grouped buddy/status context,
  active state chips, real searchable roster, unread badges, colored presence,
  empty/onboarding states (no dummy contact rows), contextual hover states.
- Rebuilt private IM: header with buddy name/presence, incoming/outgoing
  messages with timestamps, multi-line wrapping, scrolling to earlier history,
  composer, typing state and hover response on send.
- Redesigned directory rows, plus real hover/focus states wired on Windows
  WM_MOUSEMOVE and Linux X11 MotionNotify.
- Included an improved Android **UI resource kit only**, not an APK.

## Technical implementation

All desktop rendering and input management are written in Go and shared by
Windows and Linux; platform windows use native Win32 and X11 bindings.
No Go, Python, Fyne, Node or Java runtime is required by a recipient of
these compiled desktop binaries. The Linux application needs the host's
libX11 runtime and a working X11-compatible graphical display.

This is a **test build**. It is not the complete earlier Fyne/Java
feature-parity roadmap: OS notifications, secure saved tokens, system tray,
rich profile/device managers and signed installers remain outstanding.
The Go client only saves a nonsecret server URL preference.

## Verification

- Go test suite `go test -race -count=1 ./...`: **passed**
- `go vet ./...`: **passed**
- Windows x64 Win32 GUI: **cross-compiled**, PE32+ format verified;
  **not launched on a Windows computer** in this session.
- Linux x64 X11 GUI: **built and smoke-tested under Xvfb** with a
  simulated API, including signing in, opening a buddy IM, and sending
  `Nice to see the updated design!` (recorded as POST /api/messages).
- Android: XML checked for well-formedness, **no APK built**.
- No GitHub operations performed in this pass.

## Configuration

The server URL must point to a real Dokploy Beacon host, e.g.
`http://redacted.invalid:8765` (replace with your own address). The
address `127.0.0.1` refers to the computer running the desktop client.
Use HTTPS via a proper reverse proxy for networks you don't fully trust.

Source is included with the binaries for verification/reproducibility.
Compiler/font-atlas generation requires Go 1.23 and Linux X11 build headers
when building from source. Installed users do not need source build tools.
