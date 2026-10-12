# Beacon 0.9.0 native GitHub updater

## Platform independence

Beacon is one Docker container and a persistent data volume. The built-in
updater **does not know or care** whether the container was launched with
Docker Compose, Docker CLI, Portainer, Dokploy or another management system.

Update source: `https://github.com/gigabytegrove/beacon`, branch `main`.
There are **no** Docker API calls, Docker socket mounts, extra containers,
GitHub tokens, provider API keys, platform integrations, CI runners or GHCR
requirements for normal application-code updates.

## First installation / transition to 0.9.0

A Docker container whose image predates the native supervisor **cannot**
run a supervisor that isn't installed yet. It must be rebuilt or replaced
**once** from a Beacon image containing `server/launcher.py`.

For an existing instance whose Compose already builds the public repository
at `#main`, use that management tool's normal rebuild operation **once**.
If you deployed from an earlier pinned recovery SHA, you must change the pin
to `main` once. **Do not recreate or erase the existing persistent volume.**

New users can install the 0.9.0 image through their preferred ordinary
Docker/Compose deployment process. There is no dedicated platform setup.

Once 0.9.0 is running, a release that changes only Python server/application
code or web assets can update directly inside Beacon without replacing
the Docker container.

## Normal in-app update

1. Sign in as a Beacon server administrator.
2. Open **Control Center → Updates → Check GitHub**.
3. Compare the running version/commit with GitHub's `main` commit.
4. Select **Download & install**.
5. Beacon obtains GitHub's immutable commit SHA and its source tree.
6. The server downloads the source archive from GitHub over HTTPS.
   Every extracted `server/` file is checked against the Git blob hash
   in that commit's source tree. The source archive's SHA-256 is recorded.
   Unsafe paths, symlinks, malformed files, oversized archives, incomplete
   server packages, and new/changed Python dependency lists are rejected.
7. Verified application files are staged under
   `/data/beacon-updates/releases/<commit-sha>/`.
8. The native launcher detects an atomic activation request, gracefully
   stops the serving Python process and launches the new application code.
   It verifies `GET /health` returns the expected revision.
9. If the updated app fails to start, cannot serve the correct health
   response in time or exits during probation, the launcher restores the
   preceding code automatically. Use **Roll back** for manual restoration.

**The SQLite database stays at `/data/beacon.db` throughout.** Accounts,
messages and persistent settings aren't copied, deleted or replaced by
installing updated code. Migrations performed by future app versions may
be forward-only, however; administrators should continue backing up SQLite
data prior to updates. A code rollback is *not* a database downgrade.

If GitHub cannot be reached, the old server continues running.
The updater keeps only verified code in its installed-release directories.
Server-side failures appear in the Update status view.

## What native updates can and cannot replace

Automatic, without touching Docker:

- Python code under `server/`, including API endpoints and messaging logic
- Web UI, HTML/CSS/JS and bundled `server/static/` assets
- Additive, backward-compatible application migrations implemented in code

Requires rebuilding/replacing the image through whatever Docker tool users
already employ:

- Python packages added to or changed in `requirements.txt`
- Base Python runtime, Linux system packages or Docker image configuration
- The immutable bootstrap supervisor itself (`server/launcher.py`) if its
  process-management machinery changes

Those limitations come from Docker's filesystem/image lifecycle; Beacon
refuses dependency-incompatible updates rather than trying to mutate an
immutable image or install packages as an unprivileged user.

## Security and lifecycle

- GitHub source is public; no source credentials are required.
- Only HTTPS and the official GitHub API/archive hosts are contacted.
  Redirects to other destinations are refused.
- File contents are verified using Git's blob hash against the selected
  immutable Git commit, and Python syntax is compiled before activation.
- No installation shell scripts from archives are executed.
- Update controls require a signed-in administrator; ordinary members and
  unauthenticated visitors cannot check, install or request rollback.
- Native launcher holds the serving process as a child and handles SIGTERM.
- Upgrade files live in the same existing persistent volume as the database
  but separate release directories.
- Failure of a startup health check does not replace the existing database.
- The updater's short-lived download memory and supervisor process are modest;
  no second live Beacon server is required for a normal upgrade.
- A previously saved, unused provider key from older experimental versions
  is **not** used by the native updater. Remove that old key through your
  original deployment configuration or delete its obsolete file manually.

## Validation before recommending use on production

Required acceptance checks:

1. Build fresh 0.9.0 container and confirm `/health` and login work.
2. Test an account, a message, and the device/session APIs.
3. Publish a compatible code-only change to `main`.
4. Check GitHub and install via Beacon UI.
5. Confirm the container ID and database volume are unchanged, but the
   running commit has changed.
6. Simulate a malformed/broken release and verify automatic rollback.
7. Restart the container and confirm the selected release persists.
8. Exercise manual rollback without losing messages.

These are the release gates. Committed source and mocked unit tests are **not**
a substitute for a real in-container end-to-end rollout.

## Conventional Docker Compose first installation

```yaml
services:
  beacon:
    build:
      context: https://github.com/gigabytegrove/beacon.git#main
    restart: unless-stopped
    ports:
      - "8765:8765"
    volumes:
      - beacon-data:/data
volumes:
  beacon-data:
```

Do not replace an **existing** installation's volume mapping blindly; the
actual persistent volume might have a Compose-project prefix. Verify its
original mount before switching Compose definitions.
