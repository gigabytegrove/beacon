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


## Actual GitHub build runners

When GitHub-hosted runners fail before any command runs, use the **same workflows on isolated, preconfigured self-hosted build machines**. The GitHub Actions variable `BEACON_USE_SELF_HOSTED_RUNNERS=true` selects those workers for pushes, or the manual `runner=self-hosted` option selects them per run. All compiler and artifact validations remain mandatory. See [Self-hosted Build Runners](SELF-HOSTED-BUILD-RUNNERS.md). Both EXE and Linux tar.gz must actually exist before telling users they can download them.


## Locally compiled visual preview archive

The repository also contains **separately labeled premium Go Win32/X11 test clients** in `releases/previews/2026-10-11/`, with source in `clients/desktop-native-preview`. The Windows preview is packaged as a ZIP containing an EXE; the Linux preview is a tar.gz. Their checksums are listed in the preview directory and verified in tests.

This preview is **not** the same application as the full Go/Fyne primary release target described above. Build it independently using [BUILDING.md](../clients/desktop-native-preview/BUILDING.md). It compiles using native platform APIs without bundling Python or third-party Go dependencies. Windows runtime and Android APK verification remain outstanding.


## Premium full-client build expectations
The full Go/Fyne client now includes Beacon-branded theme, sign-in, roster and message cards. The separately compiled native Win32/X11 preview is not feature-equivalent to Fyne and cannot substitute for an accepted desktop build. Android source has BeaconTheme and all fourteen UI resources integrated in the actual application (v0.8.0); build the real APK before distributing it.
