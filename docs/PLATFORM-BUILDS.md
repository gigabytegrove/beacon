# Beacon platform builds — local-only

GitHub Actions is disabled and its workflow definitions have been deleted. Source-control pushes do not execute builds. All builds require actual local toolchains and completed test results.

- **Windows (full desktop):** compile Go/Fyne locally on Windows with MinGW-w64 using `scripts/build-desktop-windows.ps1`; verify the EXE on Windows.
- **Linux (full desktop):** compile Go/Fyne locally with GCC/OpenGL/X11 headers using `scripts/build-desktop-linux.sh`; verify the app on a graphical Linux machine.
- **Android:** build the Java project locally in Android Studio (SDK 35, JDK 17+) or run `scripts/build-android-windows.ps1` with Gradle 8.9; install the resulting APK.
- **Docker server:** run FastAPI tests and a local Docker image build before Dokploy deployment.

**Current result:** the full Go/Fyne executables and Android APK are **not yet verified**. Separate [Go/Win32 and Go/X11 preview builds](../releases/previews/2026-10-12/README.md) were compiled locally and the Linux preview passed a mocked-server graphical smoke test. These are limited-function test clients, not the full release. See [Build and Test](BUILD-AND-TEST.md).
