# Development and quality gates

## Principles

Beacon is self-hosted, LAN-first, text-first and entirely separate from Monita. The intended interaction model is traditional AIM: buddy list, personal presence/photos, standalone IM windows and notifications. The repository uses **large, coherent development commits** rather than tiny file-by-file commits.

Documentation is a release requirement: whenever APIs or behavior change, update the root README, relevant client docs, API reference, security/operations notes and changelog in the same changeset.

## Repository map

- `server/main.py` — authentication, sessions, messages, Docker-hosted FastAPI app
- `server/aim.py` — buddy/presence/profile/typing/sync endpoints
- `server/social.py` — private groups, aliases and mute preferences
- `server/static/index.html` — browser buddy list and pop-out conversations
- `clients/desktop/` — native Tkinter Windows/Linux client
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
