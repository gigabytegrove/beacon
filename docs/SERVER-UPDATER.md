# Beacon server updater (Dokploy Compose + GHCR)

The supported destination architecture is a **prebuilt container image** pulled
from `ghcr.io/gigabytegrove/beacon` and an administrator-only **Updates** tab in
Beacon's own web control center.

The original Git-build-based `compose.raw.yaml` and `compose.dokploy.yaml`
remain available to avoid disrupting existing deployments. Only switch to
`compose.image.yaml` **after the first image has actually been published and
pull access verified**.

## How updates work

1. An authorized developer builds and smoke-tests a release **on a local build
   machine**, then pushes versioned and `latest` tags to GHCR.
2. The server runs in Dokploy with `compose.image.yaml`, containing:
   `image: ghcr.io/gigabytegrove/beacon:${BEACON_IMAGE_TAG:-latest}` and
   `pull_policy: always`.
3. A signed-in Beacon **administrator** opens **Control Center → Updates** and
   selects **Update server**.
4. Beacon invokes Dokploy's authenticated `POST /api/compose.redeploy`.
   Dokploy pulls the tagged image and replaces the container using the existing
   `beacon-data` persistent volume.
5. After reconnection, re-open Updates to verify the reported running version,
   revision and `/health` status. A successful HTTP response to the redeploy
   request means the command was accepted, **not** that a new image was installed.

No Docker socket is mounted; no sidecar or external updater container is used.
The deployment is executed by the existing Dokploy installation.

## Publish an image (one-time initialization, then each release)

**No GitHub Actions or paid build infrastructure are used.**

On an authorized local build machine with Docker Buildx, a working build engine,
Git, and a local checkout of this repository:

```bash
# Authenticate through Docker using a locally supplied token.
# Do not paste tokens into Git, Compose files or Beacon's browser UI.
docker login ghcr.io

git pull --ff-only origin main
bash scripts/publish-server-image.sh 0.8.3
```

The publisher refuses a dirty worktree, builds a Linux image, performs an
isolated startup/health check, and only then pushes `0.8.3` and `latest`.
It does not publish Windows or Android clients.

**IMPORTANT:** Newly created GHCR packages default to private. Either make the
Beacon container package public in GitHub's Package settings or configure
Dokploy pull credentials before switching the running service from source
build to image pull. A public repository does not automatically imply a
public GHCR package. Verify an anonymous pull where possible:

```bash
docker pull ghcr.io/gigabytegrove/beacon:latest
```

If publishing has not occurred, **do not change the existing Compose service
to `compose.image.yaml`**. It would fail to pull an absent/private image.

## One-time Dokploy enrollment for the in-app updater

Configure these values **in Dokploy's existing Compose service Environment
editor** (not committed to GitHub, not sent through browser settings):

- `BEACON_DOKPLOY_URL` — the HTTPS origin of your Dokploy instance (for
  example `https://dokploy.example.net`). The container must be able to
  resolve and reach this URL with valid TLS.
- `BEACON_DOKPLOY_COMPOSE_ID` — the **actual Compose ID** for the existing
  Beacon Compose service, not its display name or container ID.
- `BEACON_DOKPLOY_API_KEY` — a Dokploy API key authorized to redeploy that
  Compose service. Treat this as a sensitive deployment credential and limit
  its privileges wherever Dokploy supports it.

The relevant Compose YAML files explicitly pass these values through
`${BEACON_DOKPLOY_...}` environment interpolation. After saving them, perform
**one initial manual redeploy** to activate the updater integration. Routine
subsequent update requests can be made through the Beacon UI.

Do not store the API key in Beacon's `server_settings` SQLite table or in
client-side JavaScript. Do not put it into GitHub source control.

## Current UX and limitations

**Control Center → Updates** is administrator-only and displays installed
version, build revision, deployment mode, and whether the updater is configured.
The Update server button requests a deployment via Dokploy. The server
rate-limits requests and disables the button if required configuration is
missing.

- The page does **not yet compare the installed image with a verified latest
  registry digest**, so clicking Update server can re-deploy the same version.
- The page shows when Dokploy accepted a request; it does **not yet track
  build/deployment stages or perform automatic rollback**. Verify the
  running release after reconnection.
- Deployment request state lives in the running process and is cleared when
  the container is replaced.
- A versioned image remains available for a manual rollback by adjusting
  `BEACON_IMAGE_TAG` in Dokploy.
- The server updater is separate from updating installed desktop EXEs and
  Android APKs.

## Recovery

If Update server reports unconfigured, verify that all three credentials are
passed into the container; Compose environment values must be interpolated
explicitly. If Dokploy rejects a request, check the Compose ID and API-key
authorization. If the new container does not become healthy, use the existing
Dokploy Deployments/Logs UI to inspect the failure and restore the previous
known-good versioned image, preserving the `beacon-data` volume.

**Never use Docker Compose's down-volume option or remove the named volume.**

- Dokploy API: https://docs.dokploy.com/docs/api/compose
- GHCR package access: https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry
