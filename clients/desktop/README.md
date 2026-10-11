# Beacon Desktop — Native Windows and Linux (v0.6.0)

The Beacon desktop client is a Python 3/Tkinter application built around the classic buddy list.

- Sign in with server URL, username/password and unique device name
- The buddy list stays in its own window; double-click a contact to open a separate IM window
- Presence indicators, status selector, unread counts, sign-on and new-message pop-up notifications
- Collapsible buddy groups with a context menu to rename/delete groups
- Right-click a buddy to set a local nickname, move to a group, mute alerts or remove them
- **+ Group** creates a new group; **+ Buddy** finds an existing account by username
- **Alerts** toggles sound; **IM pop-ups** toggles automatic new-message windows
- Photos use optional Pillow for JPEG/WebP thumbnails, or Tkinter's built-in PNG support

Requirements: Python 3.10+, Tkinter, running Beacon Docker server. Install Pillow for full photo support: \`python3 -m pip install Pillow\`.

Windows: \`py -3 clients/desktop/beacon_desktop.py\`

Linux: \`python3 clients/desktop/beacon_desktop.py\` (install \`python3-tk\` if your distribution omits Tkinter).

The client polls the server every three seconds while running. Its account token is not written to disk. This early version does not have a system tray, auto-start or native OS notification integration. Android will be a separate native client.

## Windows v0.6.0 — EXE, tray and protected sessions

Windows uses the same Beacon Docker server as Android. With the optional Windows packages installed, the client keeps polling in a system tray after its roster is closed, provides **Open Beacon** and **Quit Beacon** actions, and attempts Windows OS toast notifications for sign-ons and incoming IMs.

The sign-in screen offers **Keep me signed in**. If enabled, Beacon protects the token with Windows DPAPI under the current Windows user and stores it at `%LOCALAPPDATA%\Beacon\session.bin`. On restart it validates the session against the server before showing the buddy list. Logout and Quit remove the encrypted token and revoke the server session. Linux retains memory-only login sessions and ordinary window-close behavior.

Build on Windows with Python 3.12:

~~~powershell
py -3 -m pip install -r clients/desktop/requirements-windows.txt
py -3 -m PyInstaller --clean --onefile --windowed --name Beacon --collect-all pystray --collect-all winotify clients/desktop/beacon_desktop.py
~~~

After a successful local build: `dist/Beacon.exe`. The [Windows Actions workflow](../../.github/workflows/windows.yml) renames it `Beacon-Windows-0.6.0.exe` and uploads it as a build artifact. **A CI workflow in the repository is not a confirmed EXE** until it runs successfully. Windows may restrict toast display based on OS notification settings; Beacon falls back to its Tk pop-up when possible.
