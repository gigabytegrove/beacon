# Deploy Beacon with Dokploy (recommended)

## Important: select Git source, NOT Raw Compose

The error `failed to read dockerfile: open Dockerfile: no such file or directory` means Dokploy used **Source Type: docker raw**, which creates only the Compose YAML and does not check out the Beacon repository. With `build.context: .`, Docker cannot see the Dockerfile. Switch the Dokploy Compose service **Source** to **Git/GitHub** and connect the private `gigabytegrove/beacon` repository, branch `main`, Compose Path `./compose.dokploy.yaml`. If the service cannot change source type, create a replacement Git-sourced Compose service and retain the existing `beacon-data` volume. The Compose server builds on Dokploy; GitHub Actions is **not used**.

## First-run administrator wizard

For a fresh installation **do not set BEACON_ADMIN_PASSWORD**. Beacon generates a single-use setup code and logs it in the private Beacon container logs. Open **Dokploy → Beacon → Logs**, find `BEACON FIRST-RUN ADMIN SETUP` and copy the `SETUP CODE`. Open Beacon in your browser; its new first-run wizard asks for the code, administrator username, display name, password (minimum 12 characters), and password confirmation. After creating the administrator, sign in normally. The code is deleted after use, is never exposed by an HTTP endpoint, and the setup page cannot be used once any account exists.

Do not share the setup code, expose TCP 8765 publicly during initial configuration, or delete the `beacon-data` volume on redeploy. Existing user databases remain intact. Legacy env-provided admin credentials still work only on the *first* startup if deliberately configured; they are optional and bypass the wizard.

---

Beacon is managed by **Dokploy Docker Compose**, not by running git and docker compose from `/root/beacon` on the host. Dokploy fetches the private GitHub repo and builds the server for you. There is no requirement for a `/root/beacon` directory.

## Initial setup

1. In Dokploy, open your project (or create one), **Create Service → Compose**, and select **Docker Compose**. Do **not** select Docker Stack/Swarm: this setup uses `build:`.
2. Choose the **GitHub** source connected to the private `gigabytegrove/beacon` repository. Ensure your Dokploy GitHub integration has access to the private repo.
3. Select branch **`main`** and **Compose Path `./compose.dokploy.yaml`**. Save. The repository contains the Dockerfile and everything required to build the server image.
4. In the Compose service **Environment** tab, configure:
   - **Leave `BEACON_ADMIN_PASSWORD` unset for the first-run wizard.** Existing env-based bootstrap is optional and is supported for compatibility.
   - `BEACON_ADMIN_USERNAME=admin` (or your preferred initial administrator username)
   - `BEACON_BIND_IP=0.0.0.0` (optional; publishes port on host network; restrict via firewall), or your **actual host LAN IP** to restrict it to that interface
   - `BEACON_PORT=8765` (optional; host listening port)
5. Save environment variables and **Deploy** in Dokploy. The `beacon` service should build and enter a healthy state. Check its **Logs** and **Deployments** tabs. The Docker named volume `beacon-data` persists the SQLite database under `/data`.
6. Open `http://YOUR_DOCKER_HOST_LAN_IP:8765` and complete the one-time admin setup wizard using the code shown in Dokploy's Beacon service logs. Then sign in.

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

- **`Dockerfile` missing / Raw Compose:** Switch Dokploy Source to **Git**, not Raw. The raw Compose editor does not fetch the private Dockerfile.
- **Git access denied:** Check Dokploy's GitHub source connection has access to the private repository.
- **Compose file not found:** The Compose Path must be **`./compose.dokploy.yaml`**, not a server directory like `/root/beacon`.
- **First-run wizard missing:** Check `/api/setup/status`, confirm the updated image is running, and check the private Beacon logs for the setup code. A missing `BEACON_ADMIN_PASSWORD` is normal.
- **`dokploy-network` not found:** Verify you're deploying on a Dokploy-managed Docker host that has the external network. The regular `compose.yaml` is for standalone local Docker installations.
- **Port already in use:** Set `BEACON_PORT` to an unused host port, or switch to proxy-only binding.
- **Connection refused:** Check the Dokploy service's Logs, Deployments and health status; the host port is not listening until deployment succeeds.
- **HTTP works but chats never update:** Configure the proxy for WebSocket Upgrade on `/api/ws` and preserve the external Host header.
- **Existing data missing:** Verify you're looking at the intended Docker volume `beacon-data`; do not initialize new data over an old volume.

## Docker Compose vs Docker Stack

Choose **Compose / Docker Compose**, because the server image is built from Git with `build.context: .`. Dokploy's Docker Stack variant does not support the same build method.

See [official Dokploy Compose documentation](https://docs.dokploy.com/docs/core/docker-compose) and [Dokploy Compose example](https://docs.dokploy.com/docs/core/docker-compose/example).

## v0.7.0 client/server compatibility

All three native clients connect to this one Dokploy-hosted Beacon server. Windows, Linux and Android v0.7.0 expect the new authenticated `/api/messages/search` endpoint; redeploy the server from `main` through Dokploy before using client search. Native builds are produced locally with the manual platform build scripts, not GitHub Actions. `compose.dokploy.yaml`, the `beacon-data` persistent volume and TCP port 8765 remain unchanged.

## Beacon 0.8.0: Go desktop clients, unchanged Docker deployment

Windows and Linux clients are now built as Go/Fyne executables. **Nothing about this requires Go or Python to be installed on desktop client devices.** The server remains the single Python/FastAPI Docker Compose service on Dokploy using `./compose.dokploy.yaml`. Redeploy GitHub `main` through Dokploy to receive the server's buddy field compatibility fix. No new service, container or host directory is needed, and the existing `beacon-data` volume must remain intact.

## Early client testing

Before testing the desktop/mobile apps, use the independent [Beacon Probe](../tools/beacon-probe/README.md) to verify `/health` and optionally the authenticated API from a LAN workstation. The probe is a compiled Go diagnostic, not the GUI client. See [Build and Test](BUILD-AND-TEST.md) for local-only client build instructions. GitHub Actions is disabled.

## SQLite/presence stabilization

The backend now uses bounded SQLite connection lifetimes and a presence index added at application startup. This change is compatible with the existing `beacon-data` persistent volume; it does **not** require a new container, port, Compose filename or standalone checkout. **Back up `beacon-data` before deploying** a source commit containing database migrations, then redeploy the existing GitHub-backed Dokploy Compose service from `main`. Confirm health and two-device presence after rollout.
