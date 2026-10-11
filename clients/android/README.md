# Beacon Android — v0.7.0 source

This is Beacon's **native Android application source**, not a browser wrapper or WebView. It shares the Docker server used by the Windows, Linux and browser clients.

## Build

Open the **clients/android** directory as a project in Android Studio. Install:

- JDK 17
- Android SDK Platform 35 and matching build tools
- Android Gradle Plugin 8.7.3 (configured by this project)
- Gradle 8.9 (supported by the configured Android plugin)

Sync the Gradle project, then use **Build > Build APK(s)**. Alternatively, if Gradle 8.9 and SDK 35 are installed:

~~~bash
cd clients/android
gradle --no-daemon :app:assembleDebug
~~~

The expected **output after a successful local build** is `app/build/outputs/apk/debug/Beacon-Android-0.7.0-debug.apk`. This repository does not currently include the generated Gradle wrapper JAR or a prebuilt APK. **A device install and Gradle build have not yet been verified in this environment.**

## Features implemented in source

- Username/password authentication against a LAN IP or HTTPS proxy
- Dedicated device sessions; bearer token encrypted with an Android Keystore AES-GCM key
- Native buddy list grouped into personal buddy groups
- Profile photos, nicknames, statuses, unread counts and muting information
- Tap a buddy for a native conversation view, message sending, history and typing indicator
- Long-press a buddy to edit nickname, move to group, mute/unmute or remove them
- Create, rename and delete your personal buddy groups
- Online/Away/Busy controls
- Account password change, sign out other devices and logout
- Local Android notification channel while the app is **open**; permission requested on Android 13+

## Network and notification limitations

Without opting in, the Android client polls only while its Activity is visible. The new opt-in foreground service checks the LAN while in the background, but Android can still restrict or terminate it. Missed messages remain saved on the server.

The Android manifest intentionally enables cleartext HTTP so a local server can be addressed by `http://192.168...`. This is not encrypted and should only be used on a trusted network. Use HTTPS behind a secure reverse proxy for untrusted links. The Android client never requires a third-party messaging or push service.

## Application organization

- `app/src/main/java/net/gigabytegrove/beacon/MainActivity.java`: native screens, HTTP client, presence, buddy roster, chats, Android notifications.
- `app/src/main/java/net/gigabytegrove/beacon/SecureSession.java`: encrypted private bearer-session storage via Android Keystore.
- `app/src/main/AndroidManifest.xml`: permissions and Activity declaration.
- `app/src/main/res/drawable/ic_beacon.xml`: vector launcher/notification icon.

The release is designed for Android 8.0 (API 26) and later, targeting API 35. No audio/video or WebRTC functionality is included.

## v0.7.0: Background LAN monitoring (opt-in)

Open **Account → Turn on background notifications**. Android will show a confirmation, then start Beacon's foreground service with an ongoing **Beacon is listening on your LAN** notification and a **Stop** action. The service checks the Docker server approximately every seven seconds, uses a persisted per-session message ID cursor to catch up after brief disconnections, respects buddy mute preferences and refreshes your selected Online/Away/Busy presence. Disable it from **Account** or Stop, or sign out to end monitoring.

This is best-effort—not guaranteed background push. Android can stop the foreground service, the device can leave the LAN or enter power-saving restrictions, and force-stopping the app ends delivery. The app does not silently relaunch from boot, and it does not use Firebase or an external push server. Android 13+ notification permission is required for message alerts.

The Android manifest declares `FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_REMOTE_MESSAGING` and `foregroundServiceType="remoteMessaging"`, following [Android's official type requirements](https://developer.android.com/about/versions/14/changes/fgs-types-required). Foreground services must generally be started from an eligible user-visible context; see [Android's start restrictions](https://developer.android.com/develop/background-work/services/fgs/restrictions-bg-start).

Build with Android Studio, JDK 17, Gradle 8.9 and SDK 35. The GitHub Android workflow attempts to upload a versioned APK; no APK is considered available until that build actually succeeds.

Source: `app/src/main/java/net/gigabytegrove/beacon/BeaconMonitorService.java`.

**Server deployment:** Windows and Android share the Docker server managed via [Dokploy Compose](../../docs/DOKPLOY.md). The v0.7.0 Android foreground monitor requires `GET /api/events/latest`, so deploy v0.7.0 server first. Android APK builds are independent of the Dokploy server.

## v0.7.0 account controls and IM history

The Android Account menu now includes **My profile and photo** (display name, away/status message, Android document picker for an image), **Signed-in devices** (revoke one device), and the existing password change and sign-out-other-devices actions. Individual conversation screens have **Search**, backed by the authenticated `/api/messages/search` endpoint.

The Activity now prevents overlapping foreground refresh requests and does not persist a stale foreground/visible flag across process crashes. An incoming IM notification can open its sender's conversation after the saved session is authenticated. The background LAN monitor is still opt-in, notification-visible and may be interrupted by Android battery restrictions or LAN disconnections.

After a **successful** Android Gradle build, the expected APK filename is `Beacon-Android-0.7.0-debug.apk`. Source code and workflow configuration alone do not establish that this APK was built or tested on hardware.

## Desktop clients in v0.8.0

Windows and Linux are now **Go/Fyne native compiled applications**, not Python/Tkinter. This does not change Android's own native Java APK. All three platforms use the same Dokploy-hosted Beacon API, including multi-device sessions and buddy synchronization. The server has been updated to include nickname/group/mute fields consistently for both Android and Go desktops.

## Build APK locally if GitHub Actions is blocked

On a Windows build workstation with Android Studio/SDK 35, JDK 17+ and Gradle 8.9 installed, use `powershell -ExecutionPolicy Bypass -File .\scripts\build-android-windows.ps1` from the repository root. If Gradle CLI is not installed, open `clients/android` in Android Studio and select Build APK. The script copies a **successfully compiled** APK to `dist/` and writes SHA256. No APK is guaranteed merely because the workflow exists. See [Build and Test](../../docs/BUILD-AND-TEST.md).


## Android build runner availability

The Android workflow can now run on a dedicated Linux x64 self-hosted Actions worker with label `beacon-linux`, selected manually or via repository variable. It still performs the Java/Gradle/SDK 35 build and uploads the APK only when compilation succeeds. No APK has been validated solely because a self-hosted runner option exists. See [runner setup](../../docs/SELF-HOSTED-BUILD-RUNNERS.md).
