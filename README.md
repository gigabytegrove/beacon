# Beacon

**Beacon is a LAN-first instant messenger inspired by the classic buddy-list experience of AOL Instant Messenger.** It is entirely separate from Monita.

## v0.3.0 — Buddy List

- Self-hosted Docker server; persistent SQLite messages, accounts, buddies, avatars and read cursors
- Traditional buddy list: add a username, see online/offline/away/busy, personal status, profile photo and unread count
- **Separate conversation windows** in the browser and separate native Tkinter windows on Windows/Linux
- Real-time typing signals and presence via WebSockets; desktop uses HTTP presence polling every three seconds
- Sign-on and new-message alerts in browser (tab toasts, and browser OS notifications when permitted) and desktop (Tk pop-up toasts)
- One-to-one history, cross-device shared read cursors, missed-message catch-up API and independently revocable device sessions
- No internet relay, cloud service, media calls or Monita-specific features

## Launch the Docker server

\`\`\`bash
git clone https://github.com/gigabytegrove/beacon.git
cd beacon
cp .env.example .env
# Edit .env and replace the example admin password with a unique 12+ character secret
docker compose up -d --build
\`\`\`

Open \`http://LAN-SERVER-IP:8765\`. Log in as \`admin\` with the configured bootstrap password. Use **Create account** to add users, and **+ Buddy** to add people to your own buddy list. Click a buddy to open a separate IM conversation window. Allow pop-up windows for the Beacon origin if the browser blocks them.

### Desktop

Windows: \`py -3 clients/desktop/beacon_desktop.py\`

Linux: \`python3 clients/desktop/beacon_desktop.py\` (install \`python3-tk\` if needed).

The desktop app has a persistent buddy list and separate native conversation windows. It maintains its active presence through the server API.

## Networking and security

For direct LAN access, restrict port 8765 to trusted local IPs using your host firewall. Plain HTTP is **not** encrypted, even on a LAN. For remote or untrusted network access use a correctly configured HTTPS/WSS reverse proxy, firewall/access restrictions and a valid certificate. Do **not** directly expose this prototype to the public internet.

Passwords use scrypt with unique salts. Device tokens are randomly generated, stored only as hashes on the server and expire after 30 days. User photos are sanitized to a small JPEG by the web client before upload; the server accepts validated PNG, JPEG or WebP content up to 192 KiB. Password-authenticated sessions are separate per login, and buddy lists are user-specific. The system currently has **no end-to-end encryption**: the server can access message content.

The mobile Android application, system-tray integration, native packaged installers, and WebRTC audio/video are **not implemented yet**. Browser notifications usually require HTTPS or localhost. Native Tk pop-ups require the desktop client to remain running. Device notifications are not yet guaranteed when applications are closed.

## API

- \`POST /api/login\` JSON username/password/device_name; returns bearer token
- \`GET /api/users\` and \`GET /api/directory\` authenticated people
- \`GET /api/buddies\`, \`POST /api/buddies/{id}\`, \`DELETE /api/buddies/{id}\`
- \`PUT /api/me/profile\` display_name/status_text and \`POST /api/me/avatar\` base64 image/mime_type
- \`POST /api/presence\` JSON status = available/away/busy
- \`POST /api/typing/{recipient_id}\` JSON active, \`GET /api/typing/{peer_id}\`
- \`POST /api/messages\` recipient_id/body, \`GET /api/messages/{peer_id}\`
- \`GET /api/conversations\`, \`POST /api/conversations/{peer_id}/read\` with through_id
- \`GET /api/events?after=<message_id>&limit=200\` durable catch-up
- \`GET /api/sessions\`, \`DELETE /api/sessions/{id}\`, \`POST /api/logout\`
- WebSocket \`/api/ws\`: authenticate with first message \`{"type":"auth","token":"..."}\`, then \`{"type":"typing","recipient_id":N,"active":true}\`, \`{"type":"presence","status":"away"}\` or heartbeat text \`ping\`

Existing installation databases are migrated automatically by the server. Back up your Docker named volume before deploying changes.
