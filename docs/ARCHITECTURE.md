# Beacon architecture

## Core components

- **Docker server:** FastAPI application under `server/`, with SQLite stored on a persistent Docker volume.
- **Web client:** `server/static/index.html` is intentionally dependency-light. Buddy list and chats are separate browser windows.
- **Desktop:** `clients/desktop/beacon_desktop.py` is a native Tkinter buddy list with per-contact chat windows; it currently polls every three seconds.
- **Android:** `clients/android` is a native Java Android project with Android Keystore-backed token storage and native list/chat screens; it polls while the Activity is visible.

## Data model

SQLite tables include `users`, `sessions`, `messages`, `buddies`, `buddy_groups` and `read_cursors`. The migration functions add new columns/tables to existing databases and preserve message history.

- Authentication: password hashes in `users`, hashed session tokens in `sessions`.
- Conversations: one immutable message row with sender, recipient, text and timestamp.
- Buddy lists: directional owner-to-buddy relationship, private nickname, group and muting preferences.
- Read cursors: per account and peer, monotonically advancing last-read message ID.

## Delivery behavior

1. A device authenticates and receives its own session token.
2. A sender submits text to the server.
3. The server writes the message to SQLite and responds with its ID.
4. The server sends an in-process WebSocket notification to any currently connected sessions belonging to both sender and recipient.
5. Any device disconnected during step 4 can fetch history or use `GET /api/events?after=ID` to catch up later.
6. A device marks received messages read; the cursor is persisted at the account level.

**Important constraints:** WebSocket registries and transient typing signals currently live inside one Python process. Run only **one** Uvicorn worker/container replica for this SQLite-backed architecture. Horizontal replicas would require a shared pub/sub broker and database strategy and are unsupported.

## Presence and typing

Online status is session-based, aggregated across devices. Active sessions must refresh their presence; the server sweeper expires stale heartbeats. Typing indicators are transient and expire automatically.

## Future extension points

The existing API supports new native clients. WebRTC signaling can be added to the Docker server in a later release, with TURN as an optional connectivity component for NAT traversal. WebRTC and a managed background Android notification channel are **not present** in v0.5.0.

## v0.6.0 Windows/Android device lifecycle

Windows: optional user-bound DPAPI token storage for session restoration, native tray icon to keep the desktop client alive after closing the roster, background Tk polling and Windows OS toast notifications with fallback UI. These do not require a second server process or additional Docker containers.

Android: an explicitly opted-in `remoteMessaging` foreground service shares the Android Keystore-protected session token; it shows an ongoing notification with Stop action. The service polls the Docker server for `/api/events` after a durable local cursor and sends presence updates using the currently selected status. It pauses or stops as Android demands. No Firebase push, OS bypass, hidden boot receiver, or second Docker container is used.

Guaranteed immediate messages while force-stopped or disconnected cannot be promised by this LAN-only service.

## Dokploy server deployment

Dokploy's Git-backed **Docker Compose** service uses `./compose.dokploy.yaml` (branch `main`) to build one server container, attaches to external `dokploy-network` for proxy routing, and stores SQLite in stable Docker named volume `beacon-data`. No static `/root/beacon` directory is used. Standalone `compose.yaml` remains for non-Dokploy environments.
