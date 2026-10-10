# Beacon Desktop — Native Windows and Linux

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
