# Client parity — Beacon v0.7.0

Beacon's product target is a modern AOL Instant Messenger: buddy list, personal profiles/photos, online/away/busy status, typing indicators, individual private IMs and sign-on/message notifications. It is not Monita.

| Feature | Windows | Linux | Android | Server |
|---|---|---|---|---|
| Username/password login | Native Tk | Native Tk | Native Java | scrypt and bearer sessions |
| Secure remembered login | Optional Windows DPAPI | Optional Secret Service/keyring; no plaintext fallback | Android Keystore | independently revocable tokens |
| Buddy list, personal groups, nicknames | Yes | Yes | Yes | persistent per-account configuration |
| Contact photos and away messages | Thumbnails (Pillow) | Thumbnails (Pillow) | Android Bitmap | JPEG normalized server-side |
| One-to-one IM | Separate native windows | Separate native windows | Chat screen | persistent SQLite |
| Typing indicator | HTTP polling | HTTP polling | HTTP polling | transient five-second state |
| Presence status | HTTP heartbeat | HTTP heartbeat | HTTP/foreground monitor | multi-device aggregation |
| Search saved IM history | Conversation search view | Conversation search view | Native search dialog | authenticated search endpoint |
| Edit own profile/status/photo | Native edit + photo picker (Pillow) | Native edit + photo picker (Pillow) | Native edit + photo picker | authenticated profile endpoints |
| Revoke individual device/change password | Native dialogs | Native dialogs | Native dialogs | session revocation and password rotation |
| Native toast | Windows OS notification with Tk fallback | `notify-send` with Tk fallback | Android notification | event-history catch-up |
| Keep running in background | Optional tray | Optional tray on compatible X11/AppIndicator desktops | Explicitly user-started foreground service | single Docker server |
| Packaged app | EXE CI build workflow | tar.gz + per-user installer workflow | APK CI build workflow | Dokploy Compose |

**Reality check:** Workflow source and packaged output names do not prove artifacts have been built. Windows, Linux and Android binaries must be produced by functioning GitHub runners and installed on real machines before claiming release validation. Linux tray behavior depends on the system indicator environment; Android may terminate foreground monitoring despite user opt-in. The chat server is not end-to-end encrypted.
