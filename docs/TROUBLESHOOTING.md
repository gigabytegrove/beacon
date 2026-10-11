# Troubleshooting

## Server won't start

Run `docker compose ps` and `docker compose logs --tail=200 beacon`. Confirm `.env` has a unique bootstrap password, the data volume is writable and the host port isn't used by another program.

If Python reports a syntax error near `from .aim import router`, verify your checkout is updated to **v0.5.0 or later**: v0.4.0 accidentally contained literal escaped newlines in `server/main.py`.

## Login fails

Check the server URL, user name and case, password, and whether the device has been revoked. Updating `BEACON_ADMIN_PASSWORD` in the environment does not reset an existing administrator password. Repeated failed attempts can trigger temporary IP throttling.

## Buddies show offline

Presence only counts active sessions with recent heartbeats. The web UI sends WebSocket ping heartbeats, the desktop client uses HTTP presence updates, and Android updates status while the app is visible. Backgrounded or closed Android sessions do not guarantee online presence.

## Chat pop-up does not appear

Your browser may block network-triggered pop-up windows. Allow pop-ups for the Beacon origin or click the buddy manually. Automatic pop-up behavior is an optional local preference.

## No sound or OS notification

Browser AudioContext generally needs user interaction before playback. OS notifications depend on permission and, commonly, HTTPS/localhost. Desktop pop-ups and bells require its window to remain running. Android notifications are foreground-only at this stage.

## Reverse proxy problems

Check that HTTP API routes and `/api/ws` both reach the same service, WebSocket Upgrade is passed, and the original Host header is forwarded. Mixed-content errors occur if a page served over HTTPS tries to connect via unencrypted WebSockets.

## Android app will not build

Open `clients/android` as an Android Studio project, install Android SDK platform 35 and Gradle 8.9 / Android Gradle Plugin 8.7.3 using Android Studio, and use JDK 17. The repository currently does **not** include a generated Gradle wrapper binary or prebuilt APK. See the Android README.

## Data recovery

Use the database backup instructions in [INSTALL.md](INSTALL.md). Do not delete the named volume when attempting to fix application startup or while migrating versions.
