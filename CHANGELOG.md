# Beacon changelog

## Local-only builds — October 12, 2026

- Removed **all four GitHub Actions workflow files** (Windows, Linux, Android, server CI). Source pushes no longer initiate these builds.
- Documented required local build and verification gates, with candid separation of full Go/Fyne, Android APK and limited-feature locally compiled Win32/X11 preview executables.
- Left full client source and local/manual build scripts intact; no Python runtime is required on end-user desktops.


## 0.8.0 — Branded primary-client integration (build verification pending)

- Applied Beacon's approved navy, electric-blue and light-surface visual system to the supported Go/Fyne desktop source, including logo and theme, login card, readable errors, persisted nonsecret server address, buddy filtering, presence cards and individual IM message cards.
- Moved all 14 approved premium Android resource files into the actual app module and activated BeaconTheme in AndroidManifest.
- Updated the actual Java Activity's login, inputs, buddy rows and incoming/outgoing message bubbles to use the integrated resources, without replacing its messenger, background-monitor, session or account logic.
- Advanced Android source, local builder, workflow and source tests to 0.8.0 / versionCode 8. Updated release and client docs alongside the code.
- Preserved the full-featured Go/Fyne codebase and the separate reduced-feature Win32/X11 premium preview, avoiding silent feature removal.
- Full Go/Fyne and Android SDK builds remain UNVERIFIED until a matching build host actually compiles, installs and executes them.


## 2026-10-11 premium native UI preview import

- Imported the locally built premium Go/Win32 + Go/X11 Windows/Linux visual preview as an **independent source module**, without replacing the full-featured Go/Fyne desktop application.
- Committed the matching flat blue/navy Beacon logo image assets, rasterized layouts, generated bitmap glyph atlases, hover/focus interactions, roster/search, new-message visual states, separate IM windows and developer preview/testing utilities.
- Added the actual compiled Windows preview executable packaged inside a ZIP and Linux preview tarball, with exact SHA256 verification and explicit platform runtime limitations.
- Added desktop screenshots and native Android premium colors, drawables and XML layout **design kit**. No false claim of a complete Android APK.
- Added reproducible build instructions, preview acceptance tests, test provenance and a clear feature-parity migration plan.
- **Primary client parity remains protected:** the existing Go/Fyne app still owns the full session vault, tray, notifications, profile/device management and multi-device roadmap.


## Client synchronization and multi-device read-state hardening

- Added the native Go desktop's cursor-based `/api/events` transport: latest-ID baseline, bounded ordered catch-up, strict cursor validation and resumable delivery after transient failures.
- Changed Windows/Linux AIM-style desktop notifications from unread-count-only polling to persisted per-session event discovery, with aggregation by buddy and support for mute/automatic IM windows.
- Fixed Go and Android read receipts: only acknowledge incoming messages after the active conversation has rendered, not while background networking is still loading history.
- Guarded against updating a closed Go conversation window and suppressed repeated Android read acknowledgements until new messages arrive or a request fails.
- Added locally executed, passing Go race-detector coverage for cursor seeding, multi-page catch-up, duplicates, malformed cursor responses, cancellation, page budgets and transient HTTP errors.
- Expanded documentation and acceptance checks for read state versus message delivery. GUI/Android APK build verification is still outstanding; no native release binaries are claimed from these tests.


## Build runner recovery — zero-step Actions failures

- Added manual selection of trusted self-hosted build runners to all four Windows, Linux, Android, and server/Docker CI workflows, with exact per-OS runner labels.
- Added repository variable `BEACON_USE_SELF_HOSTED_RUNNERS=true` as an opt-in for full automatic CI on self-hosted build machines; GitHub-hosted remains the default until configured.
- Preserved every existing test, compiler invocation, checksum, Docker build and required downloadable artifact. Linux self-hosted machines must have graphics headers preinstalled rather than silently invoking sudo to modify the workstation.
- Added comprehensive build-host registration, security/isolation, troubleshooting, and actual binary acceptance guidance.
- No build success is claimed while the account has no available runner; the GitHub account owner must provision or unblock a real runner.


## v0.8.0 stabilization — server connection lifecycle, batched presence and desktop UX

- Close every SQLite connection deterministically and commit/rollback within its context; avoid leaked descriptors under frequent polling.
- Query presence for whole buddy and directory rosters in batches with a migration-safe sessions index, maintaining the original available > busy > away > offline precedence across multiple devices.
- Avoid rebuilding the Go buddy-list widget tree when contacts and groups are unchanged, preserving scroll position and lowering GUI churn.
- Return the Go client to login on a revoked or expired session during polling, clearing saved OS credentials and closing stale IM windows.
- Add regression tests for close/rollback, roster isolation, two simultaneous devices, query batching and HTTP authentication.
- Update architecture, deployment, client and test documentation. No new third-party services or containers.
- **Validation pending:** CI jobs still fail before runner startup; committed tests have not been executed in GitHub Actions.


## 0.8.0 build-readiness follow-up (no GUI release declared)

- Added one-command Windows Go/Fyne desktop builder with prerequisite validation, Go API tests and versioned executable checksum output.
- Added Linux Go/Fyne builder with graphics-header checks, binary packaging, per-user installer and checksum output.
- Added Windows Android Gradle APK builder with SDK/JDK/Gradle checks and versioned debug APK output.
- Windows/Linux CI now call those same manual builders; all three platform workflows offer manual dispatch when runners become available.
- Added Go standard-library Beacon Probe source and locally compiled Windows/Linux preflight tools for server reachability and authenticated API checks. These are **diagnostics, not GUI messenger clients**.
- Documented runner failures, build-host prerequisites, local manual builds, binary verification and release acceptance; no unverified executable has been called tested.


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
