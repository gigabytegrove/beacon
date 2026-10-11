# Beacon

**Your people. Your network.** Beacon is a LAN-first, self-hosted instant messenger with the familiar experience of AOL Instant Messenger: a buddy list, personal photos, availability, away messages, typing indicators, individual IM windows, and sign-on alerts. It is a distinct project, entirely independent of Monita.

The server runs as **one Docker container with a persistent SQLite volume**. Clients communicate through a JSON HTTP API and WebSocket events. No external hosted messaging service is needed.

## Current version: 0.5.0 (development)

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
| Sign-on and message alerts | Browser, permission-dependent | Tk window/bell while running | Local notices while app is foregrounded |
| Notifications while app is fully closed | No | No | **Not implemented** |
| Installable distributables | Browser | Source-run only | Android Studio/Gradle build required |
| WebRTC audio/video | Future | Future | Future |

**Release confidence:** The server had a Python import syntax defect in v0.4.0; v0.5.0 includes the correction, migration/security tests, and CI checks. CI runners have previously failed before running any steps in this private repository; check the current Actions status and validate on a staging instance before production deployment. Android source has not yet been APK-build or device-validated in this environment.

## Quick start

1. Install Docker Engine and Docker Compose v2.
2. Clone this repository and create your private environment file.
3. Set a **unique** bootstrap password (at least 12 characters).
4. Start the service:

~~~bash
git clone https://github.com/gigabytegrove/beacon.git
cd beacon
cp .env.example .env
nano .env
docker compose up -d --build
docker compose ps
curl -fsS http://127.0.0.1:8765/health
~~~

Open **http://YOUR-LAN-IP:8765**. Sign in with the username from `BEACON_ADMIN_USERNAME` (default `admin`) and your configured password. Create user accounts from the administrator interface, then add each other as buddies.

Use HTTPS/WSS through a properly configured reverse proxy when the network is not fully trusted. **Plain HTTP does not encrypt passwords, tokens, or messages.** Never expose the prototype's HTTP port directly to the public internet.

## Documentation

- [Server installation, upgrading and backups](docs/INSTALL.md)
- [Android application setup and limitations](clients/android/README.md)
- [Windows/Linux desktop client](clients/desktop/README.md)
- [Complete API and WebSocket protocol](docs/API.md)
- [Architecture and delivery behavior](docs/ARCHITECTURE.md)
- [Security, data protection and limitations](docs/SECURITY.md)
- [Troubleshooting and diagnostics](docs/TROUBLESHOOTING.md)
- [Development and testing](docs/DEVELOPMENT.md)
- [Changelog](CHANGELOG.md)

## Project boundaries

Beacon is deliberately a personal, text-first instant messenger. It does **not** share Monita's notification-channel or automation architecture. Group messaging, files, WebRTC audio/video, native system-tray integration and true background Android delivery are future development areas, not claims about v0.5.0.

License: no license has been selected or granted in this repository; the private repository owner retains all applicable rights.
