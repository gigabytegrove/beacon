# Beacon server updater — configured entirely in the Control Center

## Goal

Once an existing Beacon instance is running a release with the updater
integration, **routine server updates happen from Beacon itself**:

**Control Center → Updates → Build & deploy latest main.**

Do not copy/paste a new Compose file for each source update.
Do not mount the Docker socket.
Do not run a separate updater container.
Do not depend on GitHub Actions or paid build runners.

Beacon asks **your existing Dokploy service** to redeploy through Dokploy's
official API. Dokploy is already responsible for building/replacing the
container. No GHCR image is required for this mode.

## One-time bootstrap (required to install the updater)

An older running image cannot use new source code until that code is deployed
at least once. For a Dokploy Compose service already building
`https://github.com/gigabytegrove/beacon.git#main`, use the existing
Dokploy **Deploy/Rebuild** operation **once** to install Beacon 0.8.5.

This does **not** require editing or recreating Compose when it already
references `main`.

If an emergency recovery deployment is pinned to an **older commit** rather
than `main`, that pin must be removed/updated once. A pinned source will
continue rebuilding the pinned code regardless of the update button.

Preserve the existing `beacon-data` volume. **Never** choose "fresh volumes",
run `docker compose down -v`, or recreate the persistent database volume.

## Connect Dokploy in Beacon — no Compose environment editing

As a signed-in administrator:

1. Open **Control Center → Updates**.
2. Under **Connect to Dokploy**, enter the **HTTPS URL** for your Dokploy
   instance, the **Compose service ID**, and a Dokploy **API key** with access
   to that service. Use Beacon over HTTPS when entering the API key.
3. Click **Verify & save connection**. Beacon calls
   `GET /api/compose.one?composeId=...` with that key and only saves a working
   connection.
4. The **Build & deploy latest main** button becomes enabled.

Your Dokploy key is stored at
`<BEACON_DB>.updater.json` (normally
`/data/beacon.db.updater.json`) with mode `0600`, owned by the unprivileged
Beacon process. It is **not sent back to the browser** and is not stored in
the user settings database or GitHub. The persistent file survives routine
container replacement. It is not encrypted at rest; protect volume backups
and restrict the API key's permissions in Dokploy wherever supported.

The connection can be changed in the same screen. Leave the key field blank
to retain the existing key, or choose **Disconnect** to delete the saved
connection. Existing `BEACON_DOKPLOY_*` environment variables are supported
as an optional compatibility fallback, but **are no longer required**.

Dokploy's `/api/compose.one` call verifies the key can read the target
service; permission to actually redeploy is verified when the update request
is submitted.

## Routine update

1. Commit new Beacon source to `main` (or publish a newer image if the
   Compose service is explicitly configured for registry images).
2. Open **Control Center → Updates** and click **Build & deploy latest main**.
3. Beacon requests `POST /api/compose.redeploy` with:
   - `composeId` set to the saved Compose service
   - `freshVolumes` set to `false`
4. Dokploy handles the rebuild/deployment through its own pipeline. Beacon
   may disconnect briefly as its server container is replaced.
5. After reconnection, verify the installed version and
   `GET /health` (should respond `{"status":"ok"}`).

This button initiates the action. An accepted HTTP response does **not**
mean the new image has finished building or is healthy. Deployment logs and
rollback history remain available in Dokploy. Current Beacon UI does not
yet show continuous Dokploy build-stage progress or automate rollback.

The updater enforces a 120-second request cooldown to reduce duplicate jobs.
No passwords or API keys are written to logs or included in updater GET
responses.

## Source build versus GHCR

Beacon can continue using the **existing public Git-source Compose build**;
the in-app updater does not need GHCR. The optional
[GHCR image Compose](../compose.image.yaml) only becomes usable once the
image has **actually been published and pull-verified**.

The current source/build setup is fully compatible with the in-app update
flow as long as Dokploy is configured to rebuild the current Git branch when
`compose.redeploy` runs. Dokploy's default Docker Compose command includes
`up -d --build`; custom deployment commands may require adjustment.

**Do not switch to the GHCR Compose file until an image exists.**

## Troubleshooting

- **Cannot verify Dokploy:** use a valid HTTPS origin reachable from inside
  the Beacon container with a trusted certificate. HTTPS is mandatory for
  the stored integration. Check that the API key can read the Compose
  service by its actual ID.
- **Update rejected:** check API-key deployment permissions and Dokploy's
  application deployments/logs.
- **Old version keeps returning:** check that Dokploy builds `main` and is
  not pinned to a recovery commit. Confirm no custom Compose command skips
  rebuilding.
- **Database or user accounts missing:** STOP and investigate which volume
  the service mounted before changing anything. Do not initialize or delete
  volumes as a workaround.

Official Dokploy references:

- https://docs.dokploy.com/docs/api/compose
- https://docs.dokploy.com/docs/core/docker-compose
