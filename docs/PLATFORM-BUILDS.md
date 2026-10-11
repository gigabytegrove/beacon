# Beacon platform builds

## Normal users: NO Python or Go setup

Windows and Linux clients are built in CI from **Go + Fyne**, then distributed as executables. Download and launch the verified compiled application. **Do not install Python, Tkinter, pip, Go or Fyne** to run it.

| Platform | Build pipeline | Expected release artifact |
|---|---|---|
| Windows x64 | Go/Fyne + MinGW-w64, `.github/workflows/windows.yml` | `Beacon-Windows-0.8.0.exe` |
| Linux x64 | Go/Fyne + GCC/OpenGL/X11 headers, `.github/workflows/linux.yml` | `Beacon-Linux-0.8.0.tar.gz` |
| Android | Java/Android Gradle, `.github/workflows/android.yml` | Android v0.7.x debug APK |

### Windows developer build

With Go 1.23+, MinGW-w64 GCC and the Fyne graphics prerequisites installed:

```powershell
cd clients/desktop-go
go mod tidy
go test ./internal/beacon
go build -trimpath -ldflags="-s -w -H=windowsgui" -o Beacon.exe ./cmd/beacon
```

For a Windows user, the resulting EXE is run by double-clicking it. The OS may show an unsigned-executable reputation prompt until signing is implemented.

### Linux developer build

With Go 1.23+, gcc, pkg-config, OpenGL/X11 development headers:

```bash
cd clients/desktop-go
go mod tidy
go test ./internal/beacon
CGO_ENABLED=1 go build -trimpath -ldflags="-s -w" -o beacon ./cmd/beacon
```

CI bundles the binary with `clients/desktop/linux/install.sh`, `uninstall.sh`, `beacon.desktop` and `beacon.svg`. Extract the archive and run `./install.sh` as your normal user; no sudo required. The binary uses the OS's graphics stack; Linux graphics dependencies vary by distribution.

### Android developer build

Open `clients/android` in Android Studio (JDK 17, Gradle 8.9, Android SDK 35). Android remains a native Java application by design, not an embedded Python or Go desktop GUI.

## Verification and dependency locking

Go direct dependencies are pinned in `clients/desktop-go/go.mod`. The build pipeline runs `go mod tidy` to resolve and generate checksums before building. **A committed Go module and workflow do not establish that an EXE or Linux binary has actually been produced.** Verify workflow steps, artifact sizes/checksums and launch behavior on target machines. Do not call the release production-ready while GitHub runners are unavailable.

Consult [Release Checklist](RELEASE-CHECKLIST.md).

## Offline/runner-blocked build route

See [Build and Test](BUILD-AND-TEST.md) for the exact commands when GitHub-hosted runners fail before execution. Windows and Linux have local scripts in `scripts/` to build the **same native Go/Fyne client**, with SHA256 files; the Android PowerShell script builds the native Java APK. These scripts require development tools only on the build workstation. All GUI binaries are still **unverified** until compiled and installed.

The independent Go [Beacon Probe](../tools/beacon-probe/README.md) can be built with only the Go standard library and tests Dokploy server connectivity. It is **not** the messenger.
