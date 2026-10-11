# Beacon client parity — v0.8.0 Go desktop transition

Beacon is a modern AIM-style messenger, separate from Monita.

| Feature | Windows Go/Fyne | Linux Go/Fyne | Native Android Java | Server |
|---|---|---|---|---|
| Language/runtime | Compiled Go EXE, **no Python** | Compiled Go binary, **no Python** | Java APK | Python FastAPI Docker |
| Buddy list/groups/nicknames | Yes, with photos | Same Go code | Native UI | SQLite |
| Separate IM windows | Yes | Yes | Chat screen | Message history |
| Typing/presence/unread | Polling | Polling | Polling/foreground monitor | HTTP + WebSocket APIs |
| Search history | Yes | Yes | Yes | Authenticated search |
| Profile/status/photo/password | Yes | Yes | Yes | Account endpoints |
| Device/session management | Yes | Yes | Yes | Independent bearer sessions |
| OS notifications/system tray | Fyne desktop support | Fyne + desktop-dependent support | Android notifications | LAN delivery |
| Secure remembered login | Windows Credential Manager | Linux Secret Service | Android Keystore | Hashed session tokens |
| Build output | Single `.exe` | tar.gz with binary + installer | APK | Dokploy Compose |

**Reality check:** Go/Fyne eliminates Python and Go development-environment requirements **for users of compiled desktop binaries**. Windows/Linux builds still need compiler/graphics development tools on CI workers; Linux runtime graphics libraries depend on the distribution. All clients and packages still require real-world build and acceptance tests. Android is intentionally native Java rather than forced into a Go GUI.

Previous Python/Tkinter desktop source is temporarily retained for reference only. No cross-platform Go UI is currently being used to replace the Android app.
