# Beacon Android — v0.5.0 source

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

The expected **output after a successful local build** is `app/build/outputs/apk/debug/app-debug.apk`. This repository does not currently include the generated Gradle wrapper JAR or a prebuilt APK. **A device install and Gradle build have not yet been verified in this environment.**

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

**Foreground-only:** This initial Android client polls the server approximately every 3.5 seconds only while the Activity is visible. When the app is backgrounded or fully closed, it does **not** maintain a push connection, guarantee instant notifications or stay marked online. Missed messages remain on the Docker server and are fetched when the application resumes. Reliable background push without a mandatory external cloud service is a planned later phase; it needs an explicitly designed Android foreground-service/battery-management strategy.

The Android manifest intentionally enables cleartext HTTP so a local server can be addressed by `http://192.168...`. This is not encrypted and should only be used on a trusted network. Use HTTPS behind a secure reverse proxy for untrusted links. The Android client never requires a third-party messaging or push service.

## Application organization

- `app/src/main/java/net/gigabytegrove/beacon/MainActivity.java`: native screens, HTTP client, presence, buddy roster, chats, Android notifications.
- `app/src/main/java/net/gigabytegrove/beacon/SecureSession.java`: encrypted private bearer-session storage via Android Keystore.
- `app/src/main/AndroidManifest.xml`: permissions and Activity declaration.
- `app/src/main/res/drawable/ic_beacon.xml`: vector launcher/notification icon.

The release is designed for Android 8.0 (API 26) and later, targeting API 35. No audio/video or WebRTC functionality is included.
