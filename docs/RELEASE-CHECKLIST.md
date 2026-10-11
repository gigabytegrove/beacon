# Beacon multi-platform release checklist

This is a **release acceptance gate**, not a statement that the checks passed.

## Repository and docs
- [ ] One coherent change set includes server, Windows, Linux, Android, CI and documentation.
- [ ] README, changelog, CLIENT-PARITY, API, SECURITY, troubleshooting and platform READMEs agree with the actual implementation.
- [ ] `compose.dokploy.yaml` builds and deploys via Git-backed Dokploy Compose without any manually cloned `/root/beacon`.
- [ ] Document environment variables, ports, volume behavior, backup/restore and reverse-proxy WebSockets.
- [ ] Version numbers match on server, Android, Windows and Linux package names.

## Server and security
- [ ] Python syntax checks and unit/integration tests pass.
- [ ] Docker image builds; app responds to `/health` and password login.
- [ ] Account A cannot search or view B–C's private conversations.
- [ ] Search treats `%`, `_` and backslashes literally and obeys per-account visibility.
- [ ] Password change and device revocation invalidate only the intended sessions.
- [ ] Existing SQLite volume migrates without losing messages, groups, profiles or tokens.
- [ ] Multi-device unread/read state, offline catch-up, typing and presence work.

## Windows
- [ ] PyInstaller EXE artifact exists, launches, logs in and sends/receives IMs.
- [ ] Buddy list persists in tray; right-click and Open/Quit work.
- [ ] DPAPI remembered session restores only under the correct Windows account.
- [ ] Native toasts and fallback pop-up alerts work; no plaintext tokens in logs/files.
- [ ] Profile editing, device management and search work.

## Linux
- [ ] PyInstaller binary packages in tar.gz with installer, desktop entry and icon.
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
