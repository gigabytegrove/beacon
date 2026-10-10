# Beacon Desktop (Windows and Linux)

Native Python 3/Tkinter client: traditional buddy list, separately opening chat windows, status controls, typing signals and pop-up alerts.

Windows: \`py -3 clients/desktop/beacon_desktop.py\`

Linux: \`python3 clients/desktop/beacon_desktop.py\` (on Debian/Ubuntu install \`python3-tk\`).

Enter the server URL, username, password and device name. The client maintains a separate device session, polls buddy status and chat updates, and keeps secrets in memory. Double-click a buddy or select them and press **IM** to open their private chat window. Use **+ Buddy** to enter a username. The desktop client can read profile photos via the server but this initial native Tk roster renders textual buddy entries; full image thumbnails and system-tray integration are not yet available.

Run over a trusted LAN, or use HTTPS behind a reverse proxy. For reliable push notifications when a client is closed, future platform-specific integrations are required.
