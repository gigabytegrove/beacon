# Beacon

**Your people. Your network.** Beacon is a LAN-first, self-hosted instant messenger inspired by classic AOL Instant Messenger: compact buddy list, profile photos, online/away/busy status, sign-on notices, typing indicators and separate conversation windows. **Beacon is independent of Monita.**

## Current development release: 0.8.0 — Native Go desktop migration

**Windows and Linux use a shared Go/Fyne source code**, built as native executables. Users do **not** need Python, pip, a Go SDK, or to install Fyne in order to run a successfully built desktop client. The legacy Python/Tkinter prototype is retained temporarily under `clients/desktop/` for reference **only**; it is not the default client, not the release build and not required on user machines.

**Android remains a native Java/Android application**, which installs as an APK. The shared messaging **server remains Python/FastAPI in one Docker container**, deployed through Dokploy. Converting the server to Go is outside this client migration.

| Platform | Primary implementation | Distribution target |
| --- | --- | --- |
| Windows | **Go 1.23+ / Fyne 2.8.1** | `Beacon-Windows-0.8.0.exe` |
| Linux | **Same Go/Fyne code** | `Beacon-Linux-0.8.0.tar.gz` including binary and desktop entry |
| Android | Native Android Java | Android 0.7.x debug APK workflow |
| Web | HTML/CSS/JavaScript | Served by the Docker server |
| Server | Python/FastAPI/SQLite | **GitHub-backed Dokploy Docker Compose** |

The Go desktop code includes authenticated sign-in, independent device sessions, secure *optional* saved login through OS credential vaults, buddy groups and aliases, presence, contact avatars, pop-out individual conversations, unread counts, typing indicators, sign-on/message notifications, buddy management, profile/photo/password changes, device revocation and message-history search. Fyne provides platform-native-style widgets, multiple windows and system tray support.

**Verification:** Source code and CI workflows are committed as development artifacts. Compiled Windows/Linux executables are **not considered available or validated unless their actual workflows successfully run and the binaries pass target-platform testing**. Earlier GitHub Actions runs in this private repository failed before runners were allocated. Linux binaries may depend on typical system graphics/X11/OpenGL libraries provided by the operating system; no Python runtime is required.

## Deploy the server with Dokploy

This is the required server deployment method. In Dokploy create **Compose → Docker Compose** (not Stack), connect private GitHub repository `gigabytegrove/beacon`, branch `main`, with **Compose Path `./compose.dokploy.yaml`**. In Environment set `BEACON_ADMIN_PASSWORD` to a unique 12+ character secret. Click **Deploy**. The service uses external `dokploy-network` and stable persistent named volume `beacon-data`; the container listens on port 8765.

**Do not try to clone the repository into `/root/beacon` or run shell Compose commands on the Dokploy server.** Update the Compose service by redeploying GitHub `main` from the Dokploy UI. Back up the data volume first. Restrict the LAN port with firewall rules or configure HTTPS through a Dokploy Domain. See [Dokploy Guide](docs/DOKPLOY.md).

For non-Dokploy users, `compose.yaml` remains an optional standalone deployment example.

## Documentation

- [**Go desktop application — Windows and Linux**](clients/desktop-go/README.md)
- [Platform build and packaging instructions](docs/PLATFORM-BUILDS.md)
- [Native-client parity and limits](docs/CLIENT-PARITY.md)
- [Android client](clients/android/README.md)
- [Dokploy deployment, upgrades and volumes](docs/DOKPLOY.md)
- [Standalone server installation and backups](docs/INSTALL.md)
- [API and WebSocket protocol](docs/API.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Security](docs/SECURITY.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Development and testing](docs/DEVELOPMENT.md)
- [Release checklist](docs/RELEASE-CHECKLIST.md)
- [Changelog](CHANGELOG.md)
- [Legacy Python prototype (deprecated)](clients/desktop/README.md)

## Security and roadmap

Bearer tokens are user/device-specific, expire and can be revoked. Go clients **optionally** save them in Windows Credential Manager or a Linux Secret Service provider; when the secure vault is unavailable, login remains in memory only. The server stores messages in SQLite, **not end-to-end encrypted**. Plain HTTP is suitable only for a trusted LAN; HTTPS/WSS is recommended for untrusted network paths.

Real-time WebSocket push is currently implemented by the browser client; Go desktops poll at intervals for messaging and presence. Future areas: complete build/device verification, richer desktop notifications, guaranteed reconnect behavior, Android background delivery refinements, and eventual WebRTC audio/video. No unrelated Monita functionality will be added.

No license has been granted for this private repository; the owner retains rights.
