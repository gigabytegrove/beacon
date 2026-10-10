# Beacon

Beacon is a LAN-first, self-hosted text messenger. It is independent of any other messaging project.

## Initial release

- Docker server with persistent SQLite storage
- Administrator-created username/password accounts
- One-to-one text conversations with stored history
- Independent login sessions for multiple devices per user
- Live WebSocket notifications to all connected sessions, plus reconnect catch-up via message history
- Responsive web client for initial validation (native Windows, Linux and Android clients are **not yet implemented**)
- No external push provider, cloud dependency, audio or video

## Deploy

```sh
git clone https://github.com/gigabytegrove/beacon.git
cd beacon
cp .env.example .env
# Set a strong BEACON_ADMIN_PASSWORD in .env before starting.
docker compose up -d --build
```

Open `http://<docker-host-ip>:8765` on your local network. Sign in with `admin` and the password set in `.env`. The initial admin credentials are used only when the user database has no accounts. On subsequent restarts the bootstrap password is not used to reset existing accounts. Keep the environment variable defined for Compose startup, and protect `.env` as a local secret.

**Important:** Plain HTTP is suitable only on an explicitly trusted LAN. For untrusted networks, use HTTPS/WSS with a reverse proxy, firewall rules and access restrictions. Beacon does not expose a built-in public internet relay. Avoid exposing port 8765 directly to the internet.

### Security

Passwords are hashed using scrypt with unique salts; device session tokens are stored as SHA-256 hashes, not plaintext. Tokens expire after 30 days. The login endpoint has an in-memory per-IP attempt limit. Each device has its own revocable session. Local notification events reach online devices over WebSockets; OS-level background mobile notifications require a future Android integration.

### Admin API

Log in through `POST /api/login` with JSON `{"username":"admin","password":"...","device_name":"Admin browser"}`. Use the returned bearer token in `Authorization: Bearer <token>`.

Create users using `POST /api/admin/users` with `{"username":"alice","password":"a-long-private-password","display_name":"Alice"}`. List accounts using `GET /api/users`. List/revoke sessions using `GET /api/sessions` and `DELETE /api/sessions/{id}`.

`GET /health` is unauthenticated. Data persists in the `beacon-data` Docker volume.

### Architecture

The API, WebSocket endpoint, and responsive client are delivered by the single Docker container. The protocol uses JSON over HTTP and WebSocket to allow later Windows, Linux, and Android clients. Future audio/video should use WebRTC peer connections and separate server-assisted signaling/TURN infrastructure; no media stack is included here.
