# Troubleshooting

**Desktop update (v0.8.0):** Windows and Linux use the new **Go/Fyne** client under `clients/desktop-go`. Old Python/Tkinter startup commands, PyInstaller errors, and the `clients/desktop/requirements-*.txt` are legacy reference material, **not** installation requirements for end users. See [Go Desktop Client](../clients/desktop-go/README.md).

**Dokploy installations:** The absence of `/root/beacon` is expected; Dokploy fetches the Git repository itself. Use a Compose service with source `gigabytegrove/beacon`, branch `main`, Compose Path `./compose.dokploy.yaml`, admin password in the Environment tab, and inspect Dokploy's Deployments and Logs tabs. See [DOKPLOY.md](DOKPLOY.md).

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

## Windows tray and toasts

Install optional Windows dependencies with `py -3 -m pip install -r clients/desktop/requirements-windows.txt`. A tray icon is created after successful Windows login. If the tray is unavailable, closing the window quits as before. Windows notification policies can block OS toasts; Beacon uses a Tk fallback. A DPAPI session token cannot be copied to another Windows user profile. Sign in again if it cannot be decrypted.

## Android background notification delays

Enable **Account → Turn on background notifications** and look for the persistent Beacon listening notification. Grant Android 13+ notification permission. This monitoring is optional and depends on an active, permitted Android foreground service, a reachable LAN and device power-management policy. It is not available after a user force-stop, and it won't silently relaunch at boot. Tap Stop in the persistent notification to disable monitoring. Reopen Beacon to retrieve messages after a disconnected period.

## Linux tray, notifications and remembered login

Install the distro's Tkinter package and the optional dependencies in `clients/desktop/requirements-linux.txt`. Linux desktop keyring/Secret Service must be available to remember a login; otherwise the client signs in normally but only stores the bearer token in memory. A missing AppIndicator backend means close-to-tray is disabled. A working `notify-send` binary enables native notifications; otherwise Beacon shows a Tk dialog.

Extract the Linux release tarball and run `./install.sh` for an unprivileged, per-user installation. Run `./uninstall.sh` from the archive to uninstall. `~/.local/bin` must be on your PATH.

## Client profile, device manager, or conversation search

On Windows/Linux, use the Profile and Devices buttons on the buddy list or Search history in an IM window. On Android, open the Account menu for Profile/Devices and Search inside a conversation. Searches need at least two characters; they only return messages involving the signed-in account. 401 errors typically indicate revoked/expired sessions.

## Go client not launching

**Windows:** Use the verified versioned EXE from a successful Windows workflow. No Python/pip/Go installation is needed. An unsigned development binary may trigger SmartScreen; verify the artifact's origin and checksum. If secure remembered login fails, sign in again and confirm Windows Credential Manager is available.

**Linux:** Extract the versioned Go tarball, run `./install.sh` as your normal user, and launch `beacon` via your app menu or `~/.local/bin/beacon`. A graphical display and normal OpenGL/window-system shared libraries are required. Install missing system graphics packages using your distribution package manager if the loader reports a missing library. No Python runtime is required. Linux remembered login needs a Secret Service/keyring provider; it is optional, never plaintext.

**No notifications/tray:** OS desktop environments vary. In Preferences, enable/disable automatic IM windows or close-to-tray behavior. If a tray isn't exposed by the desktop environment, leave close-to-tray disabled. Beacon can still exchange messages when its roster remains open.

**Server response errors:** Re-deploy the Dokploy server from the same GitHub branch. Prior builds could omit nickname/group/muted fields in the buddy roster; v0.8.0 corrects this on the server. Android remains native Java and is deployed independently of the Go desktop package.

## Expired device sessions and heavy roster polling

When Beacon's server returns 401 for a revoked/expired token, the Go desktop now clears its secure saved login and returns to the sign-in screen. This is different from a temporary LAN interruption, which keeps the current session and displays a connectivity warning. For large buddy lists, server presence is now batched; if you see server latency, check Dokploy resource usage, `/health`, and the mounted SQLite volume rather than repeatedly restarting the container.


## Actions jobs fail before the first step

If all workflows show no runner and `steps=0`, no app tests were run. Check the owner account's Actions eligibility and billing status separately. For a genuine test/build path independent of hosted runner provisioning, register isolated self-hosted Windows/Linux machines as described in [Self-hosted Build Runners](SELF-HOSTED-BUILD-RUNNERS.md). Ensure the exact labels are present and the workers are Online; otherwise jobs queue rather than compiling.
