# Beacon Desktop (Windows / Linux)

This is a **native Tkinter desktop client** backed by Beacon's HTTP API.

## Requirements

- Python 3.10 or newer
- Tkinter (ships with the normal Python Windows installer)
- Linux: install the distro's Tkinter package, commonly `python3-tk`
- Access to a running Beacon server

No pip dependencies are required.

## Start

Windows PowerShell:

```powershell
py -3 clients/desktop/beacon_desktop.py
```

Linux:

```bash
python3 clients/desktop/beacon_desktop.py
```

Enter the Beacon server URL, username, password and a device name. Each login creates an independent server-side session. Messages are retrieved every three seconds while the client is open. The client keeps credentials only in memory, with no password or token saved to disk.

## Current limitations

This initial desktop client does not yet install itself, show tray notifications, automatically reconnect/login, or deliver background notifications. Its chat window must remain open to receive updates. It displays the most recent 100 messages in the selected conversation. The server also supports WebSockets for later push-based native client updates.

For untrusted network access use an HTTPS reverse proxy, not plain HTTP. Do not expose the server's HTTP port to the public internet.
