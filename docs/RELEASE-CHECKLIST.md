# Beacon multi-platform release checklist

This is a **release acceptance gate**, not a statement that the checks passed.

## Native GitHub server updater (0.9.0) acceptance gates

These tests apply to **every** Docker-hosted Beacon server, regardless of
its management UI. They are **not yet marked complete** by source checks.

- [ ] Build the 0.9.0 image from a clean public GitHub checkout.
- [ ] Run `bash scripts/verify-native-updater.sh`: launch through PID 1
      supervisor and verify its isolated failed-release auto-rollback.
- [ ] Verify existing users, login, messaging and WebSocket reconnect on
      a server using an unchanged persistent volume.
- [ ] Check GitHub from **Control Center → Updates** as an administrator;
      ordinary members and unauthenticated clients cannot access updates.
- [ ] Install a later application-code-only commit from the Beacon web UI
      without using Docker, Portainer or Dokploy actions.
- [ ] Verify the container ID and database volume remain unchanged, while
      `/health` and the UI report the new commit SHA.
- [ ] Restart that container and confirm the release remains active.
- [ ] Corrupt a staged source file and verify checksum rejection.
- [ ] Attempt an update changing `requirements.txt` and confirm a clean
      refusal without modifying the running server.
- [ ] Roll back to the previous code without losing a test account/message.
- [ ] Validate memory/disk usage on a small mixed-workload Docker host.
- [ ] Confirm no Docker socket mount, privileged user, sidecar, external
      registry, platform API or GitHub Actions are required for code updates.


## Repository and docs
- [ ] One coherent change set includes server, Windows, Linux, Android, CI and documentation.
- [ ] README, changelog, CLIENT-PARITY, API, SECURITY, troubleshooting and platform READMEs agree with the actual implementation.
- [ ] `compose.dokploy.yaml` builds and deploys via Git-backed Dokploy Compose without any manually cloned `/root/beacon`.
- [ ] Document environment variables, ports, volume behavior, backup/restore and reverse-proxy WebSockets.
- [ ] Server release/version.txt and Dockerfile base version agree. Windows/Linux and Android client versions are tracked independently.

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


## Runner eligibility and non-bypass requirements

- [ ] A dedicated, isolated Windows x64 and Linux x64 builder are registered **Online** in GitHub's Actions Runners list, with exact labels `beacon-windows` and `beacon-linux`, or GitHub-hosted execution has been restored.
- [ ] All four workflows executed nonzero build steps on matching runners; never accept a green status produced by skipping a required job.
- [ ] Repository variable `BEACON_USE_SELF_HOSTED_RUNNERS` only set after runners are registered and verified.
- [ ] Real Windows EXE, Linux tar.gz and Android APK are uploaded with expected names; download and inspect actual checksums and install on real devices.
- [ ] Python/Docker CI and all client tests pass, and no previous startup failures have been misrepresented as source failures.
- [ ] Build host has no production Dokploy credentials, and test runners are not running on the production Docker host.

- [ ] Self-hosted worker selection is blocked for `pull_request`; only trusted `push` or owner-triggered manual builds may execute on private builders.
- [ ] Download release artifacts within the configured 7-day retention window.


## Offline event sync and read receipt acceptance

- [ ] Go event transport tests pass with the race detector, including partial delivery and HTTP 503 retry without duplicates.
- [ ] Windows/Linux event notifications remain correct when unread is cleared on Android before the desktop poll.
- [ ] After offline reconnection, message notifications are batched by sender rather than one toast per missed message.
- [ ] Muting a buddy suppresses desktop sign-on/new-IM notifications but does not discard stored messages.
- [ ] Android foreground UI **renders** messages before sending server read receipts; Android background monitor never marks messages read.
- [ ] Go conversation closed during a fetch does not acknowledge messages or redraw a stale window.
- [ ] First login/monitor enable seeds latest cursor, avoiding months of old-message notification replay.
- [ ] A revoked session discards its event cursor and clears remembered credentials.
- [ ] Real Windows, Linux and Android binaries are successfully built and installed. Passing transport tests alone does not satisfy this gate.


## Premium client UI import and parity gate

- [ ] Verified preview Windows ZIP extracts an x64 PE32+ executable and its SHA256 matches the published hash.
- [ ] Verified preview Linux tar.gz contains an ELF x64 executable, installer and correct checksum.
- [ ] Full Win32 preview runtime test passes on a real Windows machine against Dokploy.
- [ ] Android premium XML kit has been integrated into Java Activities/adapters, compiled as APK and tested on device.
- [ ] Primary Go/Fyne desktop preserves full preexisting functionality while adopting premium branding.
- [ ] No temporary screenshot/template placeholder data appear as real contacts or conversations.
- [ ] All desktop feature-parity checks pass before making a premium preview the default.


## Premium full-client acceptance gates

- [ ] Build full Go/Fyne Windows EXE from clients/desktop-go and launch it on Windows; do not accept the limited native-preview executable as equivalent.
- [ ] Build full Go/Fyne Linux archive, launch on an actual supported desktop, and verify the real brand theme, buddy list, profile, devices, IM search, notifications and background operation.
- [ ] Verify dark text on white panels, visible focus, proper presence/away/busy indicator colors, empty states, scroll behavior and message alignment.
- [ ] Build the real Android v0.8.0 APK with Gradle and validate that all 14 premium resources package correctly.
- [ ] Install Android APK and verify sign-in, buddy/photo rendering, message bubbles, notification-to-chat navigation, device revocation and background monitor.
- [ ] Confirm existing SQLite volume, Dokploy Compose deployment and concurrent Windows/Linux/Android logins remain intact.
- [ ] Do not claim a verified release from structural source checks or from the previously built limited Win32/X11 preview binaries.
