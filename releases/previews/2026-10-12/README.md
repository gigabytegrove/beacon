# Beacon native Go test package — October 12, 2026

These are **real, locally built Win32 and X11 GUI test clients**. They are **NOT** the full-featured Go/Fyne release or native Android APK.

## Downloadable test artifacts

- `Beacon-Windows-Local-Test-0.8.1.zip`: a compiled x64 Windows PE GUI executable (SHA-256: `bf5d59939f063b6c6a9f03dd98a05c3b6cb0e486102756ae6645f920c2c365d5`).
- `Beacon-Linux-Local-Test-0.8.1.tar.gz`: compiled x64 Linux ELF/X11 GUI binary, icon and unprivileged installer (SHA-256: `1a33a502779470e154abc8a162680e5db46c22027d8679b710973217ad37be84`).

The source is at `clients/desktop-native-preview/`. This test build adds duplicate-login suppression, mute-aware incoming-message notifications, bounded cursor-based offline catch-up, account revocation recovery, Linux `notify-send` integration and a Windows alert sound. The new server simulator integration test additionally verifies that background polling does not issue read receipts.

## Verification performed locally

- `go test -race -count=1 ./...`: **PASS**
- `go vet ./...`: **PASS**
- Linux X11 GUI run under Xvfb against a simulated Beacon API: sign-in, buddy roster, separate IM, send-message: **PASS**
- Windows PE x64 GUI format: **PASS** (cross-compiled; **not** executed on a real Windows device).
- The artifacts' Git blob hashes match the local exact binary bytes.
- **Not verified:** full Go/Fyne applications, installed Windows behavior, live Dokploy compatibility, Android APK or real phone tests.

Do not relabel these binaries as the full desktop clients; see [local-only build policy](../../../docs/LOCAL-ONLY-BUILD-POLICY.md). **No GitHub Actions build or check was used.**
