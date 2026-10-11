# Beacon API v0.5.0

Base URL: `http(s)://SERVER:8765` (or your HTTPS reverse-proxy origin). JSON requests use `Content-Type: application/json`. Authenticated endpoints require `Authorization: Bearer TOKEN`.

## Authentication and accounts

| Method | Route | Request/response |
| --- | --- | --- |
| POST | /api/login | JSON `{"username":"alice","password":"...","device_name":"Android"}`; returns `token` and `user` |
| POST | /api/logout | Revokes current session |
| GET | /api/me | Current authenticated identity and session ID |
| POST | /api/me/password | `{"current_password":"...","new_password":"12+ chars"}`; revokes all other sessions |
| GET | /api/sessions | Current user's session list |
| DELETE | /api/sessions/{id} | Revokes one of the user's sessions |
| POST | /api/sessions/revoke-others | Revokes all sessions except current |
| GET | /api/users | All user directory profiles |
| POST | /api/admin/users | Admin-only create user (`username`, `password`, `display_name`) |

Session tokens are opaque bearer credentials. Keep them out of URL query strings and logs; never send them over public HTTP.

## Buddy lists and groups

| Method | Route | Description |
| --- | --- | --- |
| GET | /api/directory | Accounts available for buddy discovery, including presence |
| GET | /api/buddies | Caller-owned roster with nickname, photo, group, presence, mute, unread |
| POST | /api/buddies/{id} | Add a user to your buddy list |
| DELETE | /api/buddies/{id} | Remove them |
| PATCH | /api/buddies/{id} | Update `nickname`, `group_id`, `muted` |
| POST | /api/buddies/{id}/edit | Same operation for clients avoiding PATCH |
| GET | /api/groups | Caller-owned custom groups |
| POST | /api/groups | Create `{"name":"Friends"}` |
| PATCH | /api/groups/{id} | Rename group |
| POST | /api/groups/{id}/rename | Same rename for clients avoiding PATCH |
| DELETE | /api/groups/{id} | Delete group; moves contacts to default |

For group membership, `group_id: null` means the default **Buddies** group. Nicknames are per-user and never alter another person's profile. Muting only suppresses local alerts—it does not block incoming messages.

## Presence, typing, profile

| Method | Route | Description |
| --- | --- | --- |
| POST | /api/presence | `{"status":"available"|"away"|"busy"}` |
| PUT | /api/me/profile | `{"display_name":"Alice","status_text":"At lunch"}` |
| POST | /api/me/avatar | `{"image_base64":"...","mime_type":"image/png"}` |
| POST | /api/typing/{id} | `{"active":true|false}` |
| GET | /api/typing/{id} | Returns transient typing state |

Presence expires without device heartbeats, and a contact can remain available while one of their other devices is online. Avatar uploads are decoded and normalized server-side to JPEG.

## Messages and synchronization

| Method | Route | Description |
| --- | --- | --- |
| POST | /api/messages | `{"recipient_id":2,"body":"Hello!"}` |
| GET | /api/messages/{id} | Last 100 messages between caller and peer; optional `before` ID |
| GET | /api/conversations | All peers with unread counts |
| POST | /api/conversations/{id}/read | `{"through_id":123}` marks received messages read up to the ID |
| GET | /api/events?after=123&limit=200 | Ordered per-account message catch-up; up to 500 events |
| GET | /api/events/latest | Current account's latest persisted visible message ID, for first-run notification cursor seeding |

Messages are persisted **before** a WebSocket notification is sent. Use the message ID cursor to catch up after disconnection and deduplicate results. Read positions are shared across devices for the same account.

## WebSocket protocol

Connect to `ws(s)://SERVER/api/ws`. The **first message** must be:

~~~json
{"type":"auth","token":"OPAQUE_SESSION_TOKEN"}
~~~

The server replies with `{"type":"ready","user_id":N}` and delivers events with `type: "message"`, `"presence"`, `"profile"`, `"typing"`, or `"read_updated"`. Clients may send:

~~~json
{"type":"typing","recipient_id":2,"active":true}
~~~

~~~json
{"type":"presence","status":"away"}
~~~

Text `ping` receives text `pong` and updates the session's presence heartbeat. Send periodic heartbeats at approximately 25 seconds while connected. The server checks the HTTP-origin header for browser WebSockets.

## Errors and limits

FastAPI returns standard HTTP error codes: 401 authentication, 403 permission, 404 unknown entity, 409 conflict, 422 validation and 429 login throttling. Maximum message length: 4,000 characters. Profile status: 140 characters. Minimum password length for new accounts and password changes: 12 characters. Session expiry: 30 days. Username format: 3–32 letters, digits, dot, underscore or dash.

## Client behavior in v0.6.0

No new Docker server API endpoints are required for this update. Windows tray mode polls the existing buddy and message APIs. The Android opt-in foreground monitoring service uses `GET /api/buddies`, `GET /api/events?after=ID` and `POST /api/presence`, keeping a local cursor for at-least-once fetch and deduplication. Server 401 responses stop Android background monitoring. The HTTP interface is unchanged for desktop and web clients.

When first enabling Android background monitoring, the service requests `GET /api/events/latest` to seed its cursor before any notifications. Future checks use `/api/events?after=ID`; this avoids notifying the user about their entire existing conversation history. Both mobile and desktop clients use the same Docker-hosted API.

## v0.7.0: authenticated message search

`GET /api/messages/search?q=search+phrase&peer_id=42&limit=50` returns most recent matching messages (descending by ID). The peer ID is optional; omit it to search every conversation involving the current user. Search is authenticated, accepts 2–100 characters, caps results at 100, and treats `%`, `_`, and backslashes as literal text. It never searches other users' conversations, and does not require a separate search engine. SQLite LIKE scans may be slower in very large databases.
