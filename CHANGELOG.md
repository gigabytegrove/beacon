# Beacon changelog

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
