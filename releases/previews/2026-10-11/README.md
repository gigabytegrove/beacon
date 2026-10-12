# Beacon premium local desktop preview — October 11, 2026

This directory is for **locally compiled test binaries**, checksums and their provenance. Neither Windows nor Linux is considered a production release.

- `Beacon-Messenger-Windows-x64-Premium-20261011.exe` — Go/Win32 desktop preview, built locally, PE x64 structure verified, not exercised on a Windows PC.
- `Beacon-Messenger-Linux-x64-Premium-20261011.tar.gz` — Go/X11 desktop preview, built locally and exercised under Xvfb against a local simulated Beacon API.
- `SHA256SUMS.txt` — hashes for exact archive and Windows executable bytes.
- `BUILD-REPORT.md` — local build/test details and feature limitations.

**The premium binaries are functional UI previews, not the full-featured `clients/desktop-go` Fyne application.** They do not yet replace its credential vault, tray, notifications or profile/device management.

**Android has no APK in this preview.** The `design/android-premium/` path contains source styling/layout resources only. Do not rename a ZIP to APK.

The application requires connection to a deployed Beacon server through Dokploy. On a different Windows/Linux machine, `127.0.0.1:8765` refers to that device rather than the Docker server; enter the actual Beacon LAN address or HTTPS domain.

See [premium preview documentation](../../../docs/PREMIUM-PREVIEW.md).

GitHub's single-request upload of the raw 6.4 MB EXE failed; the Windows EXE is stored inside a **regular ZIP archive** instead. The EXE's original SHA256 is listed in `SHA256SUMS.txt`, alongside the archive SHA256. Extract the ZIP before execution.
