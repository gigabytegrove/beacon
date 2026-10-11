# Deploy Beacon with Dokploy (recommended)

Beacon is managed by **Dokploy Docker Compose**, not by running git and docker compose from `/root/beacon` on the host. Dokploy fetches the private GitHub repo and builds the server for you. There is no requirement for a `/root/beacon` directory.

## Initial setup

1. In Dokploy, open your project (or create one), **Create Service → Compose**, and select **Docker Compose**. Do **not** select Docker Stack/Swarm: this setup uses `build:`.
2. Choose the **GitHub** source connected to the private `gigabytegrove/beacon` repository. Ensure your Dokploy GitHub integration has access to the private repo.
3. Select branch **`main`** and **Compose Path `./compose.dokploy.yaml`**. Save. The repository contains the Dockerfile and everything required to build the server image.
4. In the Compose service **Environment** tab, configure:
   - `BEACON_ADMIN_PASSWORD=` followed by a **unique 12+ character secret** (required)
   - `BEACON_ADMIN_USERNAME=admin` (or your preferred initial administrator username)
   - `BEACON_BIND_IP=0.0.0.0` (optional; publishes port on host network; restrict via firewall), or your **actual host LAN IP** to restrict it to that interface
   - `BEACON_PORT=8765` (optional; host listening port)
5. Save environment variables and **Deploy** in Dokploy. The `beacon` service should build and enter a healthy state. Check its **Logs** and **Deployments** tabs. The Docker named volume `beacon-data` persists the SQLite database under `/data`.
6. If using the direct LAN port, browse to `http://YOUR_DOCKER_HOST_LAN_IP:8765`. Use the configured administrator login, create other accounts and add buddies.

The Compose file explicitly references `${BEACON_ADMIN_PASSWORD}` and the other variables, because Dokploy's Environment editor does **not** automatically inject arbitrary variables into containers. It interpolates them through the Compose configuration. <https://docs.dokploy.com/docs/core/docker-compose>

## Optional Dokploy domain / reverse proxy

The Beacon service is connected to Dokploy's external `dokploy-network`, which allows you to use the **Domains** tab. Add a Dokploy domain for service **`beacon`**, application/container port **`8765`**, and enable HTTPS/TLS. Dokploy recommends configuring domains in the Domains UI rather than hard-coding Traefik labels. Ensure WebSocket upgrades on `/api/ws` pass through the proxy.

For **proxy-only** usage, `BEACON_BIND_IP=127.0.0.1` prevents direct remote access to the published host port; Traefik still connects over the shared `dokploy-network`. For access by LAN-IP directly, use the actual LAN-facing host IP or `0.0.0.0` with a firewall restricting source networks. The latter binds on **all** host interfaces, so do not forward TCP 8765 publicly.

Beacon does not provide TLS on its raw port. Use HTTPS for networks you do not explicitly trust, and avoid publicly exposing Beacon without authentication and access controls.

## Updating through Dokploy

When a Beacon release is pushed to GitHub, open the existing Beacon Compose service in Dokploy and select **Deploy / Redeploy**. If you've enabled Dokploy Auto Deploy and granted GitHub access, pushes to `main` can trigger deployments according to your configuration. You should **not** run `git pull` or `docker compose up` from `/root` on the Dokploy host.

Dokploy rebuilds the image from the repository. The named `beacon-data` volume is not discarded when the container is replaced. **Do not choose options that delete volumes**, and do not create another Beacon service that uses the same explicit `beacon-data` name. Keep backups before upgrading, especially when the server database schema changes.

## Backups and restore

Configure Dokploy's **Volume Backups** against Docker named volume `beacon-data` and an appropriate backup destination, or perform a consistent SQLite backup from a running Beacon container. Backups contain message history, usernames, password hashes and profile images; treat them as private.

Dokploy's backup documentation: <https://docs.dokploy.com/docs/core/volume-backups>.

A restored database must be placed into the **same** persistent volume. Avoid deleting/recreating the named volume when troubleshooting. The service runs as UID 10001; restored files must remain writable by that user.

## If deployment fails

- **Git access denied:** Check Dokploy's GitHub source connection has access to the private repository.
- **Compose file not found:** The Compose Path must be **`./compose.dokploy.yaml`**, not a server directory like `/root/beacon`.
- **`BEACON_ADMIN_PASSWORD` missing:** Set it in the Dokploy Compose service Environment tab and redeploy.
- **`dokploy-network` not found:** Verify you're deploying on a Dokploy-managed Docker host that has the external network. The regular `compose.yaml` is for standalone local Docker installations.
- **Port already in use:** Set `BEACON_PORT` to an unused host port, or switch to proxy-only binding.
- **Connection refused:** Check the Dokploy service's Logs, Deployments and health status; the host port is not listening until deployment succeeds.
- **HTTP works but chats never update:** Configure the proxy for WebSocket Upgrade on `/api/ws` and preserve the external Host header.
- **Existing data missing:** Verify you're looking at the intended Docker volume `beacon-data`; do not initialize new data over an old volume.

## Docker Compose vs Docker Stack

Choose **Compose / Docker Compose**, because the server image is built from Git with `build.context: .`. Dokploy's Docker Stack variant does not support the same build method.

See [official Dokploy Compose documentation](https://docs.dokploy.com/docs/core/docker-compose) and [Dokploy Compose example](https://docs.dokploy.com/docs/core/docker-compose/example).

## v0.7.0 client/server compatibility

All three native clients connect to this one Dokploy-hosted Beacon server. Windows, Linux and Android v0.7.0 expect the new authenticated `/api/messages/search` endpoint; redeploy the server from `main` through Dokploy before using client search. Native builds are produced outside Dokploy in the matching GitHub platform workflow, not in a second container. `compose.dokploy.yaml`, the `beacon-data` persistent volume and TCP port 8765 remain unchanged.

## Beacon 0.8.0: Go desktop clients, unchanged Docker deployment

Windows and Linux clients are now built as Go/Fyne executables. **Nothing about this requires Go or Python to be installed on desktop client devices.** The server remains the single Python/FastAPI Docker Compose service on Dokploy using `./compose.dokploy.yaml`. Redeploy GitHub `main` through Dokploy to receive the server's buddy field compatibility fix. No new service, container or host directory is needed, and the existing `beacon-data` volume must remain intact.

## Early client testing

Before testing the desktop/mobile apps, use the independent [Beacon Probe](../tools/beacon-probe/README.md) to verify `/health` and optionally the authenticated API from a LAN workstation. The probe is a compiled Go diagnostic, not the GUI client. See [Build and Test](BUILD-AND-TEST.md) for handling blocked GitHub Actions and producing real client installers outside the Dokploy container.

## SQLite/presence stabilization

The backend now uses bounded SQLite connection lifetimes and a presence index added at application startup. This change is compatible with the existing `beacon-data` persistent volume; it does **not** require a new container, port, Compose filename or standalone checkout. **Back up `beacon-data` before deploying** a source commit containing database migrations, then redeploy the existing GitHub-backed Dokploy Compose service from `main`. Confirm health and two-device presence after rollout.
