# Beacon changelog

## 0.8.0 — Go-native Windows/Linux clients; Python desktop retired from releases

- Replaced the default desktop implementation with **one Go/Fyne source tree** for Windows and Linux. Installed users do not need Python/Tkinter/pip or a Go development toolchain.
- Dedicated Go application with a classic AIM buddy roster, avatar photos, sign-on and unread notifications, group/alias management, multi-window IMs, typing, presence, history/search and account/device administration.
- Added standard-library Go API transport with explicit input validation, bearer token protection, bounded HTTP responses, cross-origin redirect blocking, and direct HTTP unit/integration tests.
- Optional OS credential-vault session restoration: Windows Credential Manager and Linux Secret Service, with no plaintext fallback.
- Replaced PyInstaller workflows with native Go/Fyne builds producing a versioned Windows EXE and Linux binary archive; Linux XDG launcher and user installer preserved.
- Retained old Python desktop source under `clients/desktop/` solely for reference; its release packaging is discontinued.
- Android remains a native Java application; server remains Python/FastAPI deployed via Dokploy Compose.
- Fixed server buddy roster serialization to include saved group, nickname and muted settings for **all** clients; server version updated to 0.8.0.
- Updated repository/desktop/client parity/build/security/architecture documentation and version-contract tests.
- **Build verification:** source commit does not establish that Windows/Linux executables have been successfully built and installed. Validate GitHub runners and native target devices before release.


## 0.7.0 — Three-platform parity and client hardening

- Windows: native profile/status editor, signed-in device manager, per-chat search and saved alert preferences; continued Windows DPAPI session encryption, native toasts and tray behavior.
- Linux: new system keyring adapter for encrypted session persistence, native notifications and optional indicator tray with safe fallbacks, no plaintext token storage.
- Linux: packaged PyInstaller tar.gz with icon, XDG desktop entry, per-user install/uninstall scripts and GitHub workflow.
- Android: native profile/status editing, photo picker and image upload, device-session listing/revocation, conversation search and chat-opening message notifications.
- Android: non-overlapping foreground polls and process-local Activity visibility to avoid stale state after crashes; opt-in foreground monitor retained.
- Server: authenticated, account-scoped history search with literal LIKE wildcard handling; no external search service.
- Three-platform CI and additional search, source, preference, and contract tests.
- Root and platform READMEs, changelog, API, architecture, security and operational docs kept with the same release.
- CI artifacts and platform behavior remain unverified until actual builds and target-device tests pass.


## 0.6.0 — Windows and Android in tandem, Dokploy deployment

- Windows: optional per-user DPAPI-encrypted remembered login and launch-time session validation; hide-to-tray, Open/Quit tray actions and native toast alerts (optional runtime packages).
- Windows: PyInstaller workflow with a versioned executable name and CI artifact upload.
- Android: opt-in `remoteMessaging` foreground service with visible ongoing notification, Stop action, persisted per-session event cursor, 7-second best-effort LAN checks, muted-buddy filtering and presence heartbeats.
- Android: manifest permissions, Android 14+ required service type, Android versionCode 6 and versioned APK name.
- Added `compose.dokploy.yaml` and a full Dokploy Git-source, environment, networking and volume deployment guide; no `/root/beacon` clone is required.
- Added `GET /api/events/latest` to initialize Android's first background notification cursor without replaying old messages.
- Expanded platform tests and project/installation/API/security/troubleshooting docs for both clients.
- **Verification requirement:** do not represent source or workflows as built APK/EXE artifacts; validate on Windows and Android devices. Foreground services can still be stopped by Android.


## 0.5.0 — Native Android foundation, account security, documentation

- Added a native Java/Android client with login, Keystore-encrypted session token, LAN server selection, buddy list, groups, photos, nicknames, status, chat, typing indicators, read synchronization, local foreground notices, group/buddy editing and account actions.
- Added password change with current-password verification and automatic revocation of other sessions.
- Added an endpoint to revoke every other device's session without logging out the current device.
- Added POST aliases for group renaming and buddy editing for clients without reliable PATCH support.
- Corrected a Python import-breaking escaped newline sequence at the bottom of `server/main.py`.
- Corrected presence timeout handling to derive prior presence from actual active sessions.
- Expanded tests and project documentation.
- Limitations: Android notifications while the app is closed, APK distribution, packaged desktop installers and WebRTC remain outstanding. CI/runtime test status must be confirmed separately.

## 0.4.0 — Buddy organization and alerts

- Buddy groups, local nicknames, muted contacts, group management, synthesized browser notification tones, desktop pop-up behavior.
- Server-side normalization and validation of uploaded avatars.
- Tests for buddy ownership and group operations.

## 0.3.0 — AIM-style experience

- Dedicated buddy lists, profile pictures, typing events, online/away/busy presence, individual browser/native IM windows, and sign-on alerts.

## 0.1.0–0.2.x — Initial messaging foundation

- Docker-hosted server, user/password accounts, multiple device sessions, one-to-one message history, authenticated WebSockets, responsive browser interface and Python/Tk desktop client.
