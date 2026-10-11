# Install, upgrade, backup and restore

**Using Dokploy?** Follow [DOKPLOY.md](DOKPLOY.md) first. Dokploy fetches the private GitHub repo and builds `./compose.dokploy.yaml`; there is no `/root/beacon` checkout. Shell commands in this standalone document are for installations outside Dokploy.

## Requirements

A Linux Docker host, Docker Engine and Docker Compose v2. Beacon runs as a single container; the included Compose configuration publishes TCP port 8765 and stores SQLite data in a named volume.

## New installation

~~~bash
git clone https://github.com/gigabytegrove/beacon.git
cd beacon
cp .env.example .env
nano .env
docker compose config
docker compose up -d --build
docker compose ps
curl -fsS http://127.0.0.1:8765/health
~~~

**Before starting:** Change the sample `BEACON_ADMIN_PASSWORD` in `.env` to a unique password with at least 12 characters. Keep the file private (`chmod 600 .env` on Linux). The bootstrap account is created only when the user database is empty. Changing the bootstrap password in `.env` **does not** reset an existing account. To change a password after installation, use the authenticated `POST /api/me/password` endpoint.

Navigate to `http://YOUR-SERVER-IP:8765` and sign in. The server stores data under `/data/beacon.db` within its Docker volume.

## Existing installation upgrade

1. Back up the SQLite volume as described below.
2. Verify you have no uncommitted changes in the repository.
3. Run:

~~~bash
git pull --ff-only origin main
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 beacon
curl -fsS http://127.0.0.1:8765/health
~~~

Database migrations are additive and invoked during application startup. Backups are strongly advised even for additive migrations. Never delete the Docker volume as part of an upgrade.

## Backup (consistent SQLite snapshot)

Use SQLite's backup API while the server is running, then copy the complete backup file from the container to the host. This avoids copying a potentially inconsistent live SQLite database while it has uncheckpointed WAL data.

~~~bash
mkdir -p backups
docker compose exec -T beacon python -c 'import sqlite3; s=sqlite3.connect("/data/beacon.db"); d=sqlite3.connect("/data/beacon-backup.sqlite3"); s.backup(d); d.close(); s.close()'
CID="$(docker compose ps -q beacon)"
docker cp "$CID:/data/beacon-backup.sqlite3" "./backups/beacon-$(date +%Y%m%d-%H%M%S).sqlite3"
docker compose exec -T beacon rm -f /data/beacon-backup.sqlite3
~~~

Keep backup files access-restricted and off-host where possible, because they contain users, profile photos, password hashes, device metadata and unencrypted message history.

## Restore

**Only restore onto a stopped Beacon container; create a separate backup of the current state before replacing it.** Copy the chosen backup into the `backups/` folder in the repository. The command below resolves the exact Compose volume name from the container rather than guessing it.

~~~bash
BACKUP_FILE="beacon-YYYYMMDD-HHMMSS.sqlite3"
test -f "./backups/$BACKUP_FILE" || { echo "Backup not found"; exit 1; }
docker compose stop beacon
CID="$(docker compose ps -aq beacon)"
test -n "$CID" || { echo "Existing Beacon container not found"; exit 1; }
VOL="$(docker inspect "$CID" --format '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Name}}{{end}}{{end}}')"
test -n "$VOL" || { echo "Beacon data volume not found"; exit 1; }
docker run --rm -e BACKUP_FILE="$BACKUP_FILE" \
  -v "$VOL:/data" -v "$PWD/backups:/backup:ro" alpine:3.20 sh -ceu '
  test -s "/backup/$BACKUP_FILE"
  cp "/backup/$BACKUP_FILE" /data/beacon.db
  chown 10001:10001 /data/beacon.db
  rm -f /data/beacon.db-wal /data/beacon.db-shm
'
docker compose up -d beacon
docker compose logs --tail=100 beacon
~~~

This temporary Alpine container is used **only** during the manual restore; Beacon itself still runs in a single Docker container. Do not restore an untrusted or invalid SQLite file. Confirm the resulting account and message history before removing older backups.

## Reverse proxy

Proxy both regular HTTP requests and WebSocket `/api/ws`, preserve the external `Host` header, and set the required WebSocket Upgrade/Connection headers. Terminate TLS at the proxy with a valid certificate. Restrict incoming networks where possible, and do not expose the backend port publicly. See [Security](SECURITY.md).

## Operational checks

~~~bash
docker compose ps
docker compose logs --tail=200 beacon
curl -fsS http://127.0.0.1:8765/health
~~~

`GET /health` checks that the HTTP app is responsive; it is not a complete database, login or messaging test. Validate account sign-in and a test conversation separately.

## Windows and Android clients

Use the same server URL and user credentials on Windows and Android, with a separate device session for each installation. Windows packaging is described in [desktop README](../clients/desktop/README.md) and the [Windows Actions workflow](../.github/workflows/windows.yml). Android setup and optional background LAN monitoring are described in [Android README](../clients/android/README.md) and the [Android Actions workflow](../.github/workflows/android.yml).

Windows' remembered-session option is encrypted using Windows DPAPI. Android uses Android Keystore. Both store tokens for their own device sessions; do not copy local token files between devices. Only accept a downloadable installer when its workflow actually builds and uploads it.
