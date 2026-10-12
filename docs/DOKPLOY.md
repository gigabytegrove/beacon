# Optional: hosting Beacon with Dokploy

Beacon is a normal Docker application. **Dokploy is not required, does not
control Beacon updates, and never needs credentials inside Beacon.** This
document only describes one possible way of hosting the container. Use
[INSTALL.md](INSTALL.md) for the universal Docker instructions.

## First installation or initial 0.9.0 bootstrap

Use the existing `compose.raw.yaml` for **Raw Compose** or
`compose.dokploy.yaml` when your Dokploy Compose service uses the public
GitHub repository as its source. For Raw Compose, the remote build context
must specify a real source location:

```yaml
services:
  beacon:
    build: "https://github.com/gigabytegrove/beacon.git#main"
    restart: unless-stopped
    ports:
      - "8765:8765"
    volumes:
      - beacon-data:/data
    networks:
      - dokploy-network

volumes:
  beacon-data:
    name: beacon-data

networks:
  dokploy-network:
    external: true
```

The repository is public; GitHub authentication is **not required for
downloading source**. The exposed port and network settings are examples;
configure them for your own deployment. If port 8765 is accessible from
outside a trusted network, restrict it or configure HTTPS through the
container manager's normal reverse proxy. Preserve WebSocket upgrades at
`/api/ws`.

For a fresh database, watch the Beacon container log for
`BEACON FIRST-RUN ADMIN SETUP` and the one-time setup code. Enter it into
Beacon's first-run administrator wizard. Never put a default administrator
password in the public source or expose the setup code.

**Existing installations:** Inspect the current `/data` mount and keep
the same actual Docker volume when updating. Names such as `beacon-data`
might be prefixed by the Compose project. Do not delete or replace the
existing volume to solve a deployment error.

## Native Beacon updates — not Dokploy updates

Starting with Beacon 0.9.0, an **application-code** release is handled
inside Beacon itself:

**Control Center → Updates → Check GitHub → Download & install.**

Beacon retrieves GitHub code, verifies the selected commit, installs a
new version into the existing data volume, restarts its own web server
process, and automatically rolls back if startup health checks fail.

No Dokploy API URL, Compose service ID, Dokploy API key, GitHub personal
access token or sidecar updater is required.

If the running Beacon image is **older than 0.9.0**, perform the normal
Dokploy **Deploy/Rebuild once** to install the native launcher. This
initial upgrade is the only unavoidable Docker-management step for existing
deployments. Subsequent compatible application-code updates happen in
Beacon's own Control Center.

Base-image changes, changed Python dependencies and immutable launcher
bootstrap changes require building/replacing the Docker image through
the existing hosting tool. See [SERVER-UPDATER.md](SERVER-UPDATER.md).

## Diagnostics, backups, and ports

- **Health:** `GET /health` responds with status, version and running code
  revision.
- **First run:** Check container logs for the one-time setup code; do not
  delete `/data` to generate a new code.
- **Build fails:** Ensure the Git remote build context can be read by your
  Docker host. `build: .` requires a real checked-out Dockerfile; Raw
  Compose without a checkout needs the remote Git context above.
- **Chat live updates fail:** Ensure HTTP WebSocket upgrade support at
  `/api/ws`.
- **Data missing:** Check which Docker volume is mounted at `/data`,
  including project-scoped volume names, before changing anything.
- **Backups:** Use SQLite's online backup API or a consistent volume
  snapshot. Protect message history, profile images and credentials as
  private data.
- **Native update refused:** Check whether the GitHub commit changes
  `requirements.txt` or image/runtime dependencies. Such releases require
  an image rebuild rather than code-only activation.

Official platform docs:
[Dokploy Compose](https://docs.dokploy.com/docs/core/docker-compose) and
[Volume backups](https://docs.dokploy.com/docs/core/volume-backups).
