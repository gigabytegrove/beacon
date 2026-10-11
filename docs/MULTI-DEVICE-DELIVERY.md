# Beacon — multi-device message delivery and read state

This describes the Go desktop and native Android implementations after the cursor synchronization work. The shared server remains Python/FastAPI/SQLite in Dokploy.

## Guarantees implemented in source

Beacon stores messages in server-side SQLite. Each message has a monotonically increasing ID. `GET /api/events?after=N&limit=P` returns messages involving only the authenticated account, ordered by increasing message ID, plus `next_cursor`. A device keeps a **local in-memory message cursor for the current account session**; a temporary outage does not reset it.

The Go transport in `clients/desktop-go/internal/beacon/sync.go` provides:

- `LatestEventID`: seed the initial cursor with the latest visible message ID, avoiding historical sign-on notification floods.
- `EventBatch`: retrieve one authenticated, bounded event page. Validate strict ordering, page size and cursor consistency before returning events.
- `CatchUp`: fetch up to a bounded number of pages, deliver messages in order, and return the last **successfully processed** cursor. Interrupted calls resume from the last delivered ID, not from the beginning.
- Corrupt/negative/repeated/out-of-order message IDs cause a surfaced error instead of silent cursor advancement. The server's page contract is tested independently with Go `httptest`.

The Go buddy-list client now uses message-event catch-up for notifications rather than relying exclusively on the `unread_count` increasing. This matters when another device reads a message, clearing unread counts before the Windows/Linux client polls. Notification bursts are aggregated per buddy, local mute preferences are respected and automatic IM pop-out still works.

## Distinguish delivery, display, and read

These states are **not interchangeable**:

1. **Persisted:** the server has accepted and committed a message. The message survives offline devices and normal container restarts if the Dokploy `beacon-data` volume remains intact.
2. **Delivered to client:** the client obtained the message through history or cursor-based event sync. This alone does *not* mark it read.
3. **Read:** the user is viewing the relevant conversation and the client has rendered incoming messages. Only then should it send `POST /api/conversations/{buddy_id}/read` with the last displayed incoming message ID.

The Windows/Linux Go chat and Android foreground Activity now issue read acknowledgements **after** updating the conversation view, rather than doing so in a background network-fetch task. A background-only poll must not clear an unread badge on the user's other devices.

The server's read cursor is monotonic per `(user_id,peer_id)`; acknowledgements are account-scoped. Each client's local deduplication cursor is separate from the server's read cursor. Android's optional background foreground-service monitor may advance its event-notification cursor without changing the server's read state.

## Reconnect scenarios

| Scenario | Expected behavior |
|---|---|
| Windows/Linux disconnects briefly | Continue polling, then fetch missing event pages in ID order and notify without replaying delivered IDs |
| Many messages accumulated | Process bounded pages per poll and resume on the next poll; do not exhaust memory with one unbounded list |
| Another device marked a message read | Notification event still exists; a different client can still catch up by message ID |
| Background Android monitor is running | It may fetch and notify but does not set the message read by itself |
| User opens an IM | Render incoming messages first, then send a read receipt; duplicate receipts are suppressed locally where possible |
| Account signs out or session expires | Discard in-memory event cursor, stop polling and revoke/clear that session's credentials |
| Android force-stop, power restriction or LAN loss | Real-time notification cannot be guaranteed; server retains missed messages for retrieval when the app opens |

## Verification requirements

The Go message-event transport tests run successfully *locally* under `go test -race` using only standard-library HTTP test servers. These tests check cursor seeding, pagination, duplicate ID rejection, invalid cursor handling, partial callback failure, retry after transient HTTP failure, maximum page budget and canceled contexts. This is not a validation of the Fyne GUI.

Before releasing client binaries, also test a real deployment with the same account signed in on Windows, Linux and Android:

- Create two accounts and add each other as buddies.
- Send messages to a disconnected device; reconnect and confirm catch-up, correct ordering and no duplicate notifications.
- Read on one device and confirm the other device does not lose historical messages or incorrectly mark them read.
- Verify typing, sign-on, profile photos, message search, mute and automatic IM pop-out.
- Background and foreground the Android app while monitoring is enabled; confirm notifications and read-state behavior.
- Force-expire a session and verify that client returns to sign-in.
- Close chat windows during a pending network request and confirm no stale GUI updates or read acknowledgements.

## Release blockers, still outstanding

As of the October 11, 2026 development pass, the GUI builds remain unverified. GitHub Actions jobs in the private repository have been failing before assigning runners, while the local environment does not have the Fyne, Android and Windows GUI toolchains. **The compiled Go transport tests are not substitute Windows/Linux applications.**

Do not publish a Windows EXE, Linux archive or Android APK as tested until the full application is built, launched and verified on the respective platform. For build-host setup, see [Build and Test](BUILD-AND-TEST.md).
