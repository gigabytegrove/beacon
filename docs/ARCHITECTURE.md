# Beacon architecture

## Core components

- **Docker server:** FastAPI application under `server/`, with SQLite stored on a persistent Docker volume.
- **Web client:** `server/static/index.html` is intentionally dependency-light. Buddy list and chats are separate browser windows.
- **Desktop:** `clients/desktop-go` is the primary **Go/Fyne** Windows/Linux client, producing native executable files from shared source. The former `clients/desktop/beacon_desktop.py` is a deprecated prototype, not shipped.
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

## v0.7.0 platform architecture

`clients/desktop/platform_integration.py` is a shared Windows/Linux adapter for OS credential storage, notifications, optional tray controls and non-secret preferences. On Windows tokens can be protected with Windows DPAPI; on Linux an available desktop keyring is required for remembered login. Unavailable secure storage means **no** saved token, never a plaintext fallback.

Android retains Android Keystore sessions and a user-opted-in `remoteMessaging` foreground service; the Activity and service coordinate visibility via a process-local flag instead of an obsolete persisted value. Message notifications may carry the sender's user ID to open the relevant chat. Conversation search is handled entirely by an authenticated server SQL query.

## Go-native desktop architecture (v0.8.0)

The Go desktop client uses `clients/desktop-go/go.mod` with pinned Fyne 2.8.1 and go-keyring. The pure-Go `internal/beacon` package owns HTTP authentication, bearer sessions, buddy/groups API, typing/presence, conversation search and tests, while `cmd/beacon` owns windows, tray, notifications, dialogs and image rendering. OS-specific credential storage is provided by the native credential manager/secret service via the Go keyring library; no plaintext token fallback exists. User preference booleans may be stored by Fyne under the user's app settings.

Windows/Linux executables are **compiled by CI** (Go plus C compiler and Fyne graphics headers) and require no Python, pip or Tkinter to run. Linux runtime OpenGL/window-system libraries may depend on distribution. The application uses authenticated HTTP polling at approximately 3–3.5 seconds; future optional WebSocket push can reduce traffic but is not part of this release. Android remains native Java; all clients use one Dokploy Docker server.

The legacy Python/Tkinter GUI is not part of release packaging; it remains in the repository temporarily for reference only.

## Polling and SQLite lifecycle stabilization

Each backend request enters a managed SQLite context that commits completed writes, rolls back exceptions and closes its connection, rather than relying on Python's reference counting and delayed garbage collection. Presence lookups for directory/buddy results now batch user IDs into groups of 400; each group shares a live-connection query for all active device sessions, including aggregate status precedence (available, busy, away, offline). An additive session index supports these queries on existing Dokploy volumes.

The Fyne buddy-list view compares new roster/groups with its prior state and leaves the existing widget hierarchy untouched when data is identical, maintaining scroll position. When the API returns HTTP 401 during polling, the client invalidates remembered credentials and returns to login, rather than displaying a persistent network error.


## Native Go event catch-up and display-first receipts

Go `internal/beacon/sync.go` validates and delivers message history incrementally using server `/api/events`, with strict monotonically increasing IDs and a per-login in-memory cursor. The Windows/Linux Fyne roster runs a bounded catch-up alongside its existing presence/group refresh; new-message alerts are coalesced by contact, independent of server unread-count changes. The first pass seeds the account's latest message cursor and does not replay old messages as notifications. Only the account's received messages trigger new-IM alerts.

The Go and Android chat renderers now acknowledge read state **after** inserting incoming messages into the active conversation. Android deduplicates in-flight read IDs per buddy. Neither an event catch-up nor Android background monitoring marks messages read by itself. The existing Docker server remains single-container Python/FastAPI with SQLite durability; no separate push service or message broker is introduced.

Full semantics and acceptance tests: [Multi-device Delivery](MULTI-DEVICE-DELIVERY.md).
