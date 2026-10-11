# Beacon

**Your people. Your network.** Beacon is a LAN-first, self-hosted instant messenger with the familiar experience of AOL Instant Messenger: a buddy list, personal photos, availability, away messages, typing indicators, individual IM windows, and sign-on alerts. It is a distinct project, entirely independent of Monita.

The server runs as **one Docker container with a persistent SQLite volume**. Clients communicate through a JSON HTTP API and WebSocket events. No external hosted messaging service is needed.

## Current version: 0.7.0 (development)

| Capability | Web | Windows/Linux desktop | Android |
| --- | --- | --- | --- |
| Username/password sign-in | Implemented | Implemented | Implemented in source |
| Personal buddy list and groups | Yes | Yes | Yes |
| Buddy photos, nicknames, status | Yes | Yes | Yes |
| Separate IM conversation windows | Browser pop-ups | Native windows | Native conversation screen |
| One-to-one messages and history | Yes | Yes | Yes |
| Typing indicator | WebSocket | HTTP polling | HTTP polling |
| Online/away/busy status | Yes | Yes | Yes, while active |
| Multi-device sessions and unread synchronization | Yes | Yes | Yes |
| Sign-on and message alerts | Browser, permission-dependent | Windows OS toast or Tk alert while running in tray | Foreground notices and opt-in background LAN monitor |
| Notifications while app is fully closed | No | No | **Not implemented** |
| Installable distributables | Browser | Windows EXE packaging workflow (requires successful CI) | Android APK packaging workflow (requires successful CI) |
| WebRTC audio/video | Future | Future | Future |

**Release confidence:** The server had a Python import syntax defect in v0.4.0; v0.5.0 includes the correction, migration/security tests, and CI checks. CI runners have previously failed before running any steps in this private repository; check the current Actions status and validate on a staging instance before production deployment. Windows EXE and Android APK builds require successful platform CI and real device testing.

## Deploy with Dokploy (recommended)

**Beacon is a Git-backed Dokploy Docker Compose service.** No `/root/beacon` checkout or manual `docker compose up` is necessary on your Docker host.

In Dokploy choose **Create Service → Compose → Docker Compose** (not Stack), GitHub source `gigabytegrove/beacon`, branch `main`, **Compose Path `./compose.dokploy.yaml`**. Set `BEACON_ADMIN_PASSWORD` (unique, 12+ characters) in Dokploy's Environment tab, then **Deploy**.

The service is built from GitHub, uses external `dokploy-network` for optional Dokploy Domains, publishes configurable port 8765 on the host, and persists users and messages in named volume `beacon-data`. Set `BEACON_BIND_IP` to the host's LAN interface or firewall-restrict `0.0.0.0`. For reverse-proxy-only mode use `127.0.0.1` with a Dokploy Domain pointed to container port 8765. See [Dokploy deployment and troubleshooting](docs/DOKPLOY.md).

### Standalone Docker Compose (non-Dokploy)

For standalone installations only, use `compose.yaml` from a local repository checkout; copy `.env.example` to `.env`, set a strong bootstrap password, and run `docker compose up -d --build`. **Do not use these standalone commands for Dokploy-managed deployments.**

## Documentation

- [Dokploy deployment (primary)](docs/DOKPLOY.md)
- [Standalone install, backup and restore](docs/INSTALL.md)
- [Android application setup and limitations](clients/android/README.md)
- [Windows/Linux desktop client](clients/desktop/README.md)
- [Complete API and WebSocket protocol](docs/API.md)
- [Architecture and delivery behavior](docs/ARCHITECTURE.md)
- [Security, data protection and limitations](docs/SECURITY.md)
- [Troubleshooting and diagnostics](docs/TROUBLESHOOTING.md)
- [Development and testing](docs/DEVELOPMENT.md)
- [Client parity](docs/CLIENT-PARITY.md)
- [Platform builds](docs/PLATFORM-BUILDS.md)
- [Release checklist](docs/RELEASE-CHECKLIST.md)
- [Changelog](CHANGELOG.md)

## Project boundaries

Beacon is deliberately a personal, text-first instant messenger. It does **not** share Monita's notification-channel or automation architecture. Group messaging, files, WebRTC audio/video, Windows tray support and opt-in Android foreground monitoring are now implemented in source, but have not been verified on devices. Background delivery after Android force-stop or loss of LAN is not guaranteed.

License: no license has been selected or granted in this repository; the private repository owner retains all applicable rights.

## Paired Windows + Android release — v0.7.0

Windows now has Windows-user-scoped DPAPI session restoration, optional tray operation, Windows toast integration, and a GitHub Actions workflow for a versioned `Beacon-Windows-0.7.0.exe`. Android now has an explicitly enabled `remoteMessaging` foreground service with an ongoing notification, Stop action, a persisted event cursor, and LAN message/presence polling. Android uses the same Docker account, sessions, buddies and messages as the desktop client. No cloud notification provider is required.

The existence of the packaging workflows does **not** mean a verified EXE or APK is available. Check the individual Actions runs and artifacts. See [Windows build and tray documentation](clients/desktop/README.md) and [Android foreground-monitor documentation](clients/android/README.md).

## v0.7.0 — Windows, Linux and Android together

One cohesive three-client release, with corresponding server, packaging, tests and docs:

- **Windows:** protected login via DPAPI, tray and native notices, own-profile editing, signed-in device manager, saved IM-history search and persisted notification preferences.
- **Linux:** optional system keyring login (never plaintext), optional indicator tray, notify-send alerts, the same profile/devices/search UI as Windows, and Linux tar.gz distribution with desktop entry and per-user install/uninstall scripts.
- **Android:** native profile/status editor, photo picker/upload, device-session management, conversation search, non-overlapping refreshes and notifications that open the sender's conversation.
- **Server:** account-scoped message-history search that treats SQL wildcard characters literally.
- **Dokploy:** remains the primary Git-backed Compose deployment, with one persistent server; no manual `/root/beacon` checkout.

See [Client parity](docs/CLIENT-PARITY.md), [Platform builds](docs/PLATFORM-BUILDS.md) and the [release checklist](docs/RELEASE-CHECKLIST.md). **No installer/APK/EXE is considered validated until a successful build and device test.**
