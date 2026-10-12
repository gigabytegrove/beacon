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

## Go desktop compatibility (v0.8.0)

Windows/Linux Go clients consume the same authenticated endpoints used by Android and the browser; **no separate Go server or protocol** is required. Their `internal/beacon` transport validates the server URL, limits API response sizes, rejects cross-origin redirects and uses bearer tokens from an optional OS keyring.

Historically, SQLite-backed JSON sometimes serializes `is_admin` and `muted` as numeric `0`/`1`, while login may return JSON `true`/`false`. The Go models handle both safely. The v0.8.0 buddy roster also exposes per-account `nickname`, `group_id`, `group_name` and `muted`, correcting missing fields from earlier releases.


## Event cursor and read-state contract

`GET /api/events/latest` returns `{"last_message_id":N}` scoped to the authenticated account. Use it as an initial baseline when first enabling live notifications, so historical messages don't generate new alerts.

`GET /api/events?after=N&limit=P` returns ascending message IDs and `next_cursor` (the last returned ID, or N when there are no events). The client's cursor advances **only after messages have been accepted by its local delivery callback**. It rejects non-monotonic IDs or cursor mismatches; a temporary failure must not skip queued messages.

**Receipt semantics:** `POST /api/conversations/{peer_id}/read` with `{"through_id":N}` should be sent only after that peer's incoming message is displayed in an active chat view, never as a side-effect of background polling or merely downloading history. This ensures that Windows, Linux and Android remain synchronized without one background device improperly clearing another's unread counts. See [Multi-device Delivery](MULTI-DEVICE-DELIVERY.md).


## First-run setup (server v0.8.2)

| Method | Endpoint | Authentication | Description |
| --- | --- | --- | --- |
| GET | /api/setup/status | none | Returns only `{"setup_required": true\|false}`, never the secret code |
| POST | /api/setup | One-time setup code | Accepts `setup_code`, `username` (3–32 characters), `display_name`, `password` (at least 12 characters); creates the first admin only while the database is empty and responds 201 |

The server generates a 32-byte random setup code on the first start with an empty user table and no explicit legacy administrator password, persists it securely under the SQLite volume, and prints it to the private container logs. Invalid codes return 403, five failures within 15 minutes trigger 429 per source IP, and attempts to repeat setup after any account exists return 409. After creating the admin the code is deleted. The administrator must then sign in normally at `POST /api/login`.

Do not expose the setup code in the web API or unauthenticated logs. Avoid exposing an unclaimed Beacon instance on the public internet.
