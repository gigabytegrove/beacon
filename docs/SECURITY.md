# Security guidance and threat model

Beacon is designed for a trusted LAN first, not unprotected public internet exposure.

## In place

- Username/password login with uniquely salted scrypt password hashes.
- Long random per-device bearer tokens, stored as SHA-256 hashes in SQLite, expiring after 30 days.
- Independent device session revocation, password rotation and sign-out of other devices.
- Login attempt limiting by client IP within one running process.
- User-scoped buddy groups and nicknames, with authorization checks.
- Server-side avatar validation and JPEG normalization. The upload size is limited.
- WebSocket first-message token authentication; browser Origin/Host validation on WebSockets.
- Browser client displays message content via text nodes, avoiding direct HTML injection.
- Docker Compose drops Linux capabilities, sets no-new-privileges and uses a read-only root filesystem with a writable data volume.

## Missing or limited protections

- **No end-to-end encryption.** The server stores plaintext message history and can read conversations.
- **HTTP is not TLS.** Passwords and session tokens are exposed on unencrypted, untrusted networks.
- There is no packaged certificate, automatic TLS deployment, federation, internet relay or full security audit.
- IP-based login throttling is per-process and not durable across restarts; it should not be the only defense for public exposure.
- Login session tokens remain valid until revoked or expired. Android stores them encrypted via the Android Keystore; browser tokens reside in sessionStorage; the Tk desktop keeps tokens in memory.
- Android allows cleartext HTTP to support LAN IP installations. Use HTTPS when passing through any untrusted segment.
- Android foreground polling is **not** a complete background notification system.
- The current WebSocket connection registry is in-memory and assumes one process. Do not scale to multiple workers without a shared broker.
- The product does not yet implement identity verification or contact requests before buddy addition.

## Deployment checklist

1. Use a unique initial admin password and keep `.env` protected.
2. Restrict port 8765 with host/firewall or LAN VLAN rules. Do not public-forward it.
3. Use HTTPS/WSS with a real certificate for remote or untrusted connections.
4. Configure the proxy to pass the correct Host and WebSocket Upgrade headers.
5. Keep Docker host, images and reverse proxy patched.
6. Backup SQLite data securely and verify restore procedures.
7. Revoke a lost device through account sessions; change your password if credentials may have leaked.
8. Avoid posting tokens, password values and full logs in issue reports.

## Vulnerability reporting

Until a dedicated security contact is designated, do not disclose exploitable flaws in public issues. Use GitHub's private vulnerability-reporting feature if enabled for the repository, or contact the repository administrator through an established private channel.
