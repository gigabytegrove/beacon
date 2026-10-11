# Development and quality gates

## Principles

Beacon is self-hosted, LAN-first, text-first and entirely separate from Monita. The intended interaction model is traditional AIM: buddy list, personal presence/photos, standalone IM windows and notifications. The repository uses **large, coherent development commits** rather than tiny file-by-file commits.

Documentation is a release requirement: whenever APIs or behavior change, update the root README, relevant client docs, API reference, security/operations notes and changelog in the same changeset.

## Repository map

- `server/main.py` — authentication, sessions, messages, Docker-hosted FastAPI app
- `server/aim.py` — buddy/presence/profile/typing/sync endpoints
- `server/social.py` — private groups, aliases and mute preferences
- `server/static/index.html` — browser buddy list and pop-out conversations
- `clients/desktop-go/` — **primary Go/Fyne Windows and Linux native client**; stdlib Go API/tests
- `clients/desktop/` — deprecated Python/Tkinter source, reference only; not packaged
- `clients/android/` — Android Java source and Android Gradle project
- `tests/` — Python API integration tests
- `docs/` — installation, security, API, architecture and troubleshooting
- `.github/workflows/ci.yml` — server, JavaScript syntax and Python tests
- `.github/workflows/android.yml` — Android debug APK build when GitHub runner capacity is available

## Server tests

With Python 3.12:

~~~bash
python3 -m pip install -r requirements-dev.txt
python3 -m compileall -q server tests clients/desktop
python3 -m pytest -q
docker build -t beacon-local .
~~~

JavaScript syntax:

~~~bash
python3 -c "from pathlib import Path; html=Path('server/static/index.html').read_text(); Path('/tmp/beacon-browser.js').write_text(html.split('<script>',1)[1].split('</script>',1)[0])"
node --check /tmp/beacon-browser.js
~~~

## Android

Open `clients/android` in Android Studio and select Build > Make Project or Build APK. See its README for Gradle/JDK/SDK versions and known background-notification limitations.

## Before tagging a release

Confirm tests and Docker build pass; install onto a staging volume; verify two users on two devices, device revocation, offline catch-up, presence, typing, group/nickname/mute behavior, browser IM pop-ups and Android navigation. Check documentation links and the changelog. Never claim a release was runtime-validated when the GitHub runner did not execute.

## v0.6.0 paired-client release gates

Every substantive Windows/Android update includes matching client code, platform packaging workflows, regression tests and project documentation. The Windows workflow `.github/workflows/windows.yml` builds a PyInstaller EXE on `windows-latest`. The Android workflow builds the Gradle APK on `ubuntu-latest`. Run both on actual target devices to verify tray, Windows toast behavior, Windows-user DPAPI session restoration, Android foreground monitoring, user consent, Stop action, sign-out/revocation and offline message catch-up.

GitHub Actions job failures with no runner assigned and no executed steps are infrastructure failures—not evidence of successful or failing application tests. Never call an installer verified until a platform runner builds it and the resulting binary has been tested.

## Dokploy release requirement

Dokploy is the primary deployment target. Server/Docker environment changes must update `compose.dokploy.yaml`, `docs/DOKPLOY.md` and the README **in the same cohesive release commit**. Use a Git-backed Dokploy Compose service with Compose Path `./compose.dokploy.yaml`, not manual `git pull` into `/root/beacon`. Keep the standalone `compose.yaml` functional for other environments.

## Three native client release gates, v0.7.0

Windows, Linux and Android are now built and documented **in tandem**. A major release must include complete client, server, platform packaging, tests and updated documentation. CI workflows: `windows.yml`, `linux.yml`, `android.yml`, plus server `ci.yml`. New tests include `test_message_search.py`, `test_desktop_platform.py`, and `test_repository_contract.py`.

Use [client parity](CLIENT-PARITY.md), [platform build instructions](PLATFORM-BUILDS.md), and [the release checklist](RELEASE-CHECKLIST.md). In particular, do not call APK/EXE/Linux binaries validated if GitHub did not allocate any build runner or if no artifact exists.

## 0.8.0 desktop Go migration and quality gates

Windows and Linux binaries are built from the same `clients/desktop-go` source tree, not Python/Tkinter. Go dependencies are pinned to Fyne 2.8.1 and go-keyring 0.2.8 in `go.mod`. The Windows and Linux workflows run `go mod tidy`, `go test -race ./internal/beacon` and native `go build` with the platform C/graphics development environment. Application users install **only the compiled release artifact**.

The API package has no GUI dependency and is covered by Go `httptest` security/transport regressions. The Python CI workflow continues testing the **Docker server**, not a Python desktop release. No new documentation or instructions should direct users to `py -3 clients/desktop/beacon_desktop.py` for the supported desktop client.

Developer build commands and limitations: [Platform Builds](PLATFORM-BUILDS.md). Runtime/feature gates: [Release Checklist](RELEASE-CHECKLIST.md). Do not claim a successful Go compilation or package until CI has allocated a runner, completed build steps and produced inspectable artifacts. Go module checksums should be committed once a dependency-resolving environment is available.

## Manual build route and CI startup failures

Client build workflows now delegate to `scripts/build-desktop-windows.ps1` and `scripts/build-desktop-linux.sh`, and include `workflow_dispatch`. Android has `scripts/build-android-windows.ps1` for local workstations. They create checksummed binaries only if the compiler/Gradle succeeds. Neither source files nor empty Actions jobs count as successful builds. See [Build and Test](BUILD-AND-TEST.md).

The separate `tools/beacon-probe/main.go` uses only Go's standard library; it can be compiled without Fyne to test a Dokploy server. Never confuse it with the Windows/Linux GUI client.

## Database/session/roster regression gate

Tests in `tests/test_connection_and_presence.py` validate that SQLite handles close after context exit, failed transactions roll back, buddy/directory presence aggregates correctly across independent devices, no unauthorized roster access succeeds, and multiple contacts are resolved in a single batched SQL presence query. These tests complement Go transport tests and the existing FastAPI integration suite.

Before calling Beacon test-ready, run `python -m pytest -q` against the real server environment, build the Docker image, verify its Dokploy persistent volume survives redeploy, and compile/install the native Windows/Linux and Android clients. The source review is **not** equivalent to a successful CI or GUI runtime test.

Blocked GitHub Actions: follow [runner recovery](GITHUB-ACTIONS-RUNNER-RECOVERY.md) for account checks or the zero-cost local build alternative. Do not change application versions simply to retrigger an unassigned job.

## Four CI pipelines / runner selection

CI workflow files are `.github/workflows/{ci,windows,linux,android}.yml`. All four enforce tests/build/artifact checks regardless of location. The default `runs-on` is hosted; when the GitHub Actions repository variable `BEACON_USE_SELF_HOSTED_RUNNERS=true` is set or the manual-dispatch `runner=self-hosted` input is chosen, labels `beacon-windows` and `beacon-linux` select dedicated build workers. Do not use the production Dokploy host as a general-purpose Actions runner. See [Self-hosted Build Runners](SELF-HOSTED-BUILD-RUNNERS.md).

Self-hosted runner selection is **not permitted for pull_request events** to avoid executing untrusted PR code on private machines. Uploadable EXE/tar.gz/APK artifacts have 7-day retention; store release checksums separately when they are fully verified.


## Event cursor transport: independently executed Go tests

`clients/desktop-go/internal/beacon/sync.go` introduces `LatestEventID`, `EventBatch`, and `CatchUp`. The standard-library `httptest` regressions in `sync_test.go` verify account cursor seeding, multi-page catch-up, rejecting repeated/out-of-order events and invalid cursors, retry without duplicate delivery after a 503, callback interruption, bounded pages and cancellation. These tests were run locally with `go test -race -count=1 ./internal/beacon` and `go vet ./internal/beacon`.

This **only verifies the Go API package**, not the Fyne windows or Android APK. The full Fyne/Gradle build gate still must execute successfully before client downloads are considered accepted. See [Multi-device Delivery](MULTI-DEVICE-DELIVERY.md).
