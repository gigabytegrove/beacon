# Beacon local-build policy — effective October 12, 2026

**GitHub Actions is disabled for Beacon. All four previous workflow definitions have been removed from `.github/workflows/`.**

GitHub remains source control and an optional destination for **already built and verified** release artifacts. A source commit must not automatically create, rebuild, or publish a Beacon executable.

## Build rules

1. Build the full-featured Windows/Linux desktop application locally from `clients/desktop-go`, with Go/Fyne dependencies and OS-specific GUI toolchains installed **on the build machine only**. End users do not install Go or Python.
2. Build the native Android APK locally from `clients/android` using Android SDK/Gradle. Neither a screenshot nor an Android resource pack is an installable APK.
3. Run the server's Python/FastAPI tests and build the Docker image locally before deploying to Dokploy. The server remains one Compose service and uses its existing volume.
4. Run automated tests, verify executable formats and file hashes, and install/test on the target OS.
5. Add build logs, SHA-256 hashes, and honest release-status notes with any uploaded binaries. **Never rename the limited-feature Win32/X11 preview as a full Go/Fyne desktop client.**

## Locally verified preview status (not the full release)

On October 12, a revised standalone Go/Win32 and Go/X11 preview was compiled locally without GitHub Actions. Go tests passed with the race detector; a Linux Xvfb smoke test covered login, contact roster, separate IM window and message sending to a simulated Beacon API. The preview added duplicate-login prevention, cursor-based incoming-message catch-up, mute-aware native notification attempts, expired-session cleanup and regression tests. Windows binary compiled to a PE32+ GUI executable but has not been run on Windows. This is **not a full Fyne build**.

**Full Go/Fyne and Android builds remain unverified.** This environment lacks cached Fyne modules, required Linux OpenGL/X11 development headers, a Windows GUI cross-compiler for Fyne, and Android SDK/Gradle; package downloads are unavailable. No claim of complete native release should be made until those artifacts actually exist.

### Local commands

- Full Windows GUI: `powershell -ExecutionPolicy Bypass -File scripts/build-desktop-windows.ps1` on a Windows build workstation.
- Full Linux GUI: `bash scripts/build-desktop-linux.sh` on a Linux build workstation with Go and Fyne build prerequisites.
- Android APK: `powershell -ExecutionPolicy Bypass -File scripts/build-android-windows.ps1` on Windows with Android tooling, or build from Android Studio.
- FastAPI server: `python -m pytest -q`, `docker build -t beacon-local .` in a suitable build host.
- Fully offline standard-library native preview source: `clients/desktop-native-preview`, which does not depend on Fyne but has fewer features.

Any previous documentation referring to running or enabling GitHub Actions workflows is **historical only**, not the active deployment/build process.
