# Beacon multi-platform release checklist

This is a **release acceptance gate**, not a statement that the checks passed.

## Repository and docs
- [ ] One coherent change set includes server, Windows, Linux, Android, CI and documentation.
- [ ] README, changelog, CLIENT-PARITY, API, SECURITY, troubleshooting and platform READMEs agree with the actual implementation.
- [ ] `compose.dokploy.yaml` builds and deploys via Git-backed Dokploy Compose without any manually cloned `/root/beacon`.
- [ ] Document environment variables, ports, volume behavior, backup/restore and reverse-proxy WebSockets.
- [ ] Server (v0.8.0) and Windows/Linux Go package names (v0.8.0) match; Android native Java release is tracked independently (v0.7.x until rebuilt).

## Server and security
- [ ] Python syntax checks and unit/integration tests pass.
- [ ] Docker image builds; app responds to `/health` and password login.
- [ ] Account A cannot search or view B–C's private conversations.
- [ ] Search treats `%`, `_` and backslashes literally and obeys per-account visibility.
- [ ] Password change and device revocation invalidate only the intended sessions.
- [ ] Existing SQLite volume migrates without losing messages, groups, profiles or tokens.
- [ ] Multi-device unread/read state, offline catch-up, typing and presence work.

## Windows
- [ ] **Go/Fyne** Windows EXE artifact exists, launches, logs in and sends/receives IMs; no Python runtime or pip needed.
- [ ] Buddy list persists in tray; right-click and Open/Quit work.
- [ ] DPAPI remembered session restores only under the correct Windows account.
- [ ] Native toasts and fallback pop-up alerts work; no plaintext tokens in logs/files.
- [ ] Profile editing, device management and search work.

## Linux
- [ ] **Go/Fyne** Linux binary packages in tar.gz with installer, desktop entry and icon; no Python runtime or pip needed.
- [ ] Install/uninstall scripts work as unprivileged user.
- [ ] Buddy list and separate IM windows work on target desktop environments.
- [ ] Secure keyring login is optional and never falls back to plaintext tokens.
- [ ] Tray feature degrades gracefully without AppIndicator support.
- [ ] `notify-send` alert or Tk fallback works on supported systems.
- [ ] Profile editing, device management and search work.

## Android
- [ ] Gradle APK is produced and installed (Android 8 through target SDK versions).
- [ ] Login, buddy list, photo picker/upload, IM, history and search work.
- [ ] Device/session management and own-profile edits work.
- [ ] Explicitly enabled foreground monitor shows required ongoing notification.
- [ ] Background message alert opens the relevant conversation.
- [ ] First monitoring run seeds a cursor instead of replaying old messages.
- [ ] Logout/revocation stops the monitor and clears the local token.
- [ ] Android battery policy, force-stop and LAN disconnect are accurately documented.

## Rollout
- [ ] Backup the Dokploy `beacon-data` volume before deploying schema changes.
- [ ] Verify Dokploy health, HTTP routes and WebSocket upgrades through reverse proxy.
- [ ] Test simultaneous logins on Windows, Linux and Android.
- [ ] Publish only verified binaries with their build checksums; don't claim a passing CI run when no runner was assigned.

## Go native migration acceptance

- [ ] Go `internal/beacon` transport tests pass on Windows and Linux CI.
- [ ] Fyne windows, tray, dialogs and credential store compile against pinned Fyne 2.8.1.
- [ ] The old Python/Tkinter client is not packaged or required for Windows/Linux.
- [ ] Windows binary launches on a clean PC without Python/Go/Qt/Node installers.
- [ ] Linux binary runs on supported graphical desktops with standard system graphics libraries, without Python.
- [ ] Numeric and JSON boolean `muted`/`is_admin` server responses decode correctly.
- [ ] Buddy groups/nicknames/mute/unread fields are returned after a real Dokploy server deployment.
- [ ] Release artifacts have platform-specific SHA256 hashes and have been manually tested.

## Alternate build and download verification

- [ ] GitHub-hosted Actions runner allocation restored **or** native client compiled on a supported build workstation using `scripts/build-desktop-windows.ps1`, `scripts/build-desktop-linux.sh` and `scripts/build-android-windows.ps1`.
- [ ] Windows Go/Fyne EXE actually exists; record its SHA256 and test it on a clean Windows computer.
- [ ] Linux Go/Fyne archive actually exists; verify tar contents and install/run on an actual Linux desktop.
- [ ] Android APK actually exists; install on a test phone and verify background-monitor consent.
- [ ] Optional Beacon Probe succeeds against the live Dokploy server; do not count it as a GUI test.

## Stabilization acceptance

- [ ] Existing Dokploy volume migrates with the additive `idx_sessions_presence` index intact.
- [ ] Repeated polling by several devices doesn't accumulate open SQLite descriptors.
- [ ] A forced exception in a SQLite context rolls back changes and closes its connection.
- [ ] 400 or fewer directory contacts require just one presence SELECT rather than N.
- [ ] Available, busy, away and offline are accurately aggregated when one user has multiple devices.
- [ ] Windows/Linux buddy list retains scroll position between unchanged refreshes.
- [ ] An expired/revoked session returns to the login UI and clears the remembered token.
- [ ] Server tests, native GUI builds and real-device validation actually run before publication.
