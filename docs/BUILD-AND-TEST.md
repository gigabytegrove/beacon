# Beacon: build and test the clients without GitHub-hosted runners

Last checked: **October 11, 2026**.

## Verified environment facts

GitHub Actions jobs in the private `gigabytegrove/beacon` repository have repeatedly returned failure **before runner allocation**, with zero executed steps and no usable build logs. A retry of the previous Windows/Linux workflows also failed at that stage. This does **not** prove the Go/Fyne code compiles or fails; it indicates CI cannot currently execute it.

The assistant's isolated local build environment has Go 1.23 and GCC, but **no access to proxy.golang.org or the private repository over the network**, no cached Fyne dependencies, no Windows MinGW cross-compiler, no Android SDK/Gradle, and no OpenGL development headers. Hence it cannot produce or certify the native Windows/Linux GUIs or Android APK. Do not represent uncompiled source as downloadable clients.

### Downloadable, actually compiled diagnostics

The optional **Beacon Probe** is a *separate, standard-library Go connectivity tester*, not the desktop messenger. Windows x64 and Linux x64 diagnostic binaries were compiled locally on October 11, 2026, and the Linux binary passed health-only and authenticated smoke tests against a local simulated Beacon API. The Windows PE build was format-checked but cannot be launched inside the Linux environment.

Source: [tools/beacon-probe](../tools/beacon-probe/main.go). It tests server health and optionally signs in, checks account endpoints and revokes its disposable login. It never sends a message.

## Windows: build the actual Go GUI

**For whoever builds the application** (not ordinary users), install Go 1.23+ and MSYS2/MinGW-w64 GCC (on a Windows development workstation with network access), then clone the private repository and run:

```powershell
cd "$HOME\beacon"
powershell -ExecutionPolicy Bypass -File .\scripts\build-desktop-windows.ps1
```

The script verifies prerequisites, runs `go mod tidy`, tests the Go HTTP client, compiles the actual Go/Fyne Windows executable, checks output size and writes a SHA256 file. If it succeeds, retrieve `dist/Beacon-Windows-0.8.0.exe`. **End users run the EXE without Go, GCC, Python, Fyne SDK or pip.**

A failed compile will report a real compiler error, unlike the current GitHub startup failures. Do not hide build errors with `-SkipTests` unless deliberately isolating a build failure.

## Linux: build the actual Go GUI

On an ordinary Linux development workstation with Go, GCC, pkg-config and system OpenGL/X11 development headers:

```bash
git clone https://github.com/gigabytegrove/beacon.git
cd beacon
bash scripts/build-desktop-linux.sh
```

Output after a successful build: `dist/Beacon-Linux-0.8.0.tar.gz` with per-user installer, desktop entry and checksum. Standard Linux graphics runtime libraries and a display are still required on the target desktop; Python is not.

## Android: build the actual native Java APK

On a Windows development workstation with Android Studio, SDK 35, JDK 17+ and Gradle 8.9 installed:

```powershell
cd "$HOME\beacon"
powershell -ExecutionPolicy Bypass -File .\scripts\build-android-windows.ps1
```

The output after a successful build is `dist/Beacon-Android-0.7.0-debug.apk` plus checksum. Alternatively, open `clients/android` in Android Studio and select Build APK. These are **debug builds**, not signed Play Store releases.

## GitHub Actions alternative

The Windows, Linux and Android workflows support manual **workflow_dispatch** as well as normal source-triggered builds. They now delegate Windows/Linux packaging to the **same versioned build scripts** used on development workstations. When hosted runners work again, Actions uploads binaries and checksum files. Otherwise, build on a suitably provisioned Windows/Linux workstation and test the outputs locally.

**GitHub runner remediation:** In GitHub, inspect **Settings → Billing and licensing / Budgets and alerts / Actions** for unpaid charges, quota or spending blocks. Also check **Settings → Actions → General** for runner eligibility; if GitHub still provides no runner and no logs, contact GitHub Support with the run IDs. The zero-step failures alone do not prove billing is the cause.

## Install and acceptance tests

Deploy the Docker server first through Dokploy's Git Compose service (`./compose.dokploy.yaml`); never require a clone under `/root/beacon`. From a LAN machine run the Probe to verify the server can be reached. Then install the compiled GUI clients and manually test two users, independent devices, buddy photos, sign-on/off, away, typing, messages, search, notification windows, background behavior and logout/revocation. See [Release Checklist](RELEASE-CHECKLIST.md).

**Do not declare Beacon production-ready until the clients actually compile and run on Windows, Linux and Android.**

## Stabilization-specific tests

The new `tests/test_connection_and_presence.py` exercises SQLite connection closure, rollback and multi-device buddy presence, including the batched query count. These are tests to run, **not** tests reported as passing. Use `python -m pytest -q` on a build workstation with the project requirements installed. The Go desktop's unauthorized-session recovery and scroll-preserving refresh also require actual Windows/Linux GUI testing. When GitHub jobs fail with no runner, use the documented manual build scripts; do not interpret no-step failures as successful builds.

For step-by-step account/permission checks when GitHub never assigns a runner, use [GitHub Actions runner recovery](GITHUB-ACTIONS-RUNNER-RECOVERY.md). Zero-step failures do not establish a source-code build failure.