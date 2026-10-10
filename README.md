# Beacon

**Beacon — an AIM-inspired instant messenger for your own LAN.** Classic buddy lists and individual IM windows backed by modern HTTP/WebSocket APIs and a private Docker server. Beacon is **not** Monita and shares no Monita functionality.

## v0.4.0 — Buddy organization and notifications

### Server

- Username/password authentication (scrypt), individually revocable 30-day device sessions and SQLite persistence
- One-to-one chat, cross-device read positions and durable message history
- Live WebSocket typing and presence with away/busy/available state and sign-on/off updates
- Profile photos are checked, decoded and normalized server-side to JPEG using Pillow (max original 4 megapixels; max upload 192 KiB)
- **Private buddy groups** per user, rename/delete group without deleting contacts
- **Local buddy nicknames**, per-buddy notification muting, editable group membership
- Multi-user authorization checks so one account cannot rearrange another account's groups or contacts

### Classic AIM interface

- Compact buddy-list window with collapsible groups, photo thumbnails, online/offline indicators, away messages and counters
- Click a buddy to open their own conversation window; multiple independent IM windows
- Typing indicators, sign-on and message notification tones (original synthesized chimes; no copyrighted AIM sound files)
- Preferences to silence sounds or try auto-opening new IM windows
- Windows/Linux native Python/Tkinter buddy list and separate chat windows; right-click to set nicknames, group membership, mute/remove a buddy
- Incoming desktop IM window pop-ups, sign-on alerts and optional desktop bell notifications

## Server install or upgrade

\`\`\`bash
git clone https://github.com/gigabytegrove/beacon.git
cd beacon
cp .env.example .env
# Edit .env and set your own unique 12+ character initial admin password.
docker compose up -d --build
\`\`\`

For an existing checkout, take a **backup of the Docker data volume** before updating, then:

\`\`\`bash
git pull --ff-only origin main
docker compose up -d --build
\`\`\`

Open \`http://SERVER-LAN-IP:8765\`. The default initial username is \`admin\`. Configure the bootstrap password in \`.env\`; after the first successful account creation the server will not reset it on restart. Protect the \`.env\` file as a secret. The service uses a Docker named volume for data and performs additive table/column migrations on boot.

**LAN security:** Restrict port 8765 with firewall rules. HTTP does not encrypt passwords or messages in transit. For any untrusted LAN or access through the internet, deploy behind an HTTPS/WSS reverse proxy with appropriate network access controls. Beacon does not offer end-to-end encryption or an internet relay. Do not expose its HTTP service directly to the public internet.

### Windows/Linux desktop

Windows PowerShell:
\`\`\`powershell
py -3 clients/desktop/beacon_desktop.py
\`\`\`

Linux:
\`\`\`bash
python3 clients/desktop/beacon_desktop.py
\`\`\`

Tkinter is required (\`python3-tk\` on many Linux distros); optional Pillow adds JPEG/WebP buddy thumbnails. The native desktop client does not require Electron. Device credentials remain only in memory. The desktop client currently uses 3-second API polling for updates.

### Notes

- Browser pop-up blockers may prevent automatic IM window creation from incoming network events. Click an alert or buddy manually if blocked.
- Browser sound playback may need a click to enable the AudioContext. Browser OS notifications generally require HTTPS or localhost plus notification permission.
- Native desktop IM alerts and sign-on sounds currently use Tkinter pop-up windows and the platform bell, rather than a system-tray service.
- Android app, native packaged installers, file transfers and WebRTC audio/video are **not yet implemented**.

## API quick reference

Authenticate: \`POST /api/login\` (username, password, device_name). Pass the returned session token using \`Authorization: Bearer TOKEN\`.

- \`GET /api/directory\`, \`GET /api/buddies\`, \`POST /api/buddies/{id}\`, \`DELETE /api/buddies/{id}\`
- \`GET /api/groups\`, \`POST /api/groups\` (name), \`PATCH /api/groups/{id}\` (name), \`DELETE /api/groups/{id}\`
- \`PATCH /api/buddies/{id}\` (nickname, muted, group_id; null group_id uses the default group)
- \`PUT /api/me/profile\`, \`POST /api/me/avatar\`, \`POST /api/presence\`
- \`POST /api/typing/{recipient_id}\`, \`GET /api/typing/{peer_id}\`
- \`POST /api/messages\`, \`GET /api/messages/{id}\`, \`GET /api/events?after=ID\`
- \`GET /api/conversations\`, \`POST /api/conversations/{peer_id}/read\`
- \`GET /api/sessions\`, \`DELETE /api/sessions/{id}\`, \`POST /api/logout\`
- WebSocket \`/api/ws\` auth-first JSON protocol for presence, typing and messages

## Tests

\`\`\`bash
python3 -m pip install -r requirements-dev.txt
python3 -m pytest -q
\`\`\`

CI performs syntax checks, unit/integration tests, and a Docker image build.
