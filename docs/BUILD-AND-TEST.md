# Beacon builds and tests — local-only

**GitHub Actions is not used.** Every workflow file was removed. See [local-only policy](LOCAL-ONLY-BUILD-POLICY.md).

## Full Windows Go/Fyne client (not yet build-verified)

On a **Windows build workstation** with Go and MinGW-w64 GCC installed, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-desktop-windows.ps1
```

Require successful Go tests, a real .exe, its SHA-256, and installation testing on a Windows PC. Ordinary users will not require Go or Python.

## Full Linux Go/Fyne client (not yet build-verified)

On a Linux build workstation with Go, GCC and Fyne OpenGL/X11 development prerequisites:

```bash
bash scripts/build-desktop-linux.sh
```

Run Go race tests, confirm the built ELF library dependencies, install the app through its archive's unprivileged installer, and run the actual GUI.

## Native Android Java client (APK not yet built)

Open `clients/android` in Android Studio with SDK 35 and JDK 17+ and build the debug APK, or run `scripts/build-android-windows.ps1` with Android SDK and Gradle 8.9 installed on the Windows build computer. Install and test on a real device. No Android APK is produced by the Go desktop build.

## Python/FastAPI server and Dokploy

On a build workstation with Python requirements and Docker, run `python -m pytest -q`, `docker build -t beacon-local .`, then deploy the existing Git-backed `compose.dokploy.yaml` through Dokploy after a volume backup. No independent container is required for desktop builds.

## Locally compiled, reduced-feature native Go preview

Source: `clients/desktop-native-preview/`; build locally with `go test -race -count=1 ./...` and the Go toolchain. Its [October 12 test artifacts](../releases/previews/2026-10-12/README.md) were actually compiled for Windows and Linux. This **does not** satisfy the full Go/Fyne and Android acceptance gates.
