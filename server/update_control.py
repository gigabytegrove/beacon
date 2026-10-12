"""Native, Docker-platform-independent GitHub code updater for Beacon.

Admin-only APIs. Only official public GitHub repository source is accepted.
Every downloaded application file is checked against its immutable Git blob.
Updates are installed into the persistent /data volume; the image-installed
supervisor switches versions, verifies startup health and rolls back failures.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import stat
import tarfile
import tempfile
import threading
import time
from pathlib import Path, PurePosixPath
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request as URLRequest, build_opener

from fastapi import BackgroundTasks, HTTPException, Request

REPO = "gigabytegrove/beacon"
GITHUB_API = "https://api.github.com/repos/" + REPO
VALID_HOSTS = frozenset(("api.github.com", "github.com", "codeload.github.com"))
COMMIT = re.compile(r"^[0-9a-f]{40}$")
MAX_TARBALL = 18 * 1024 * 1024
MAX_TOTAL_EXTRACTED = 32 * 1024 * 1024
MAX_FILES = 256
STAGING_LOCK = threading.Lock()
STATUS_LOCK = threading.RLock()


class SafeGitHubRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlsplit(newurl)
        if parsed.scheme != "https" or parsed.hostname not in VALID_HOSTS:
            raise ValueError("GitHub redirected the update to an untrusted destination")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _root():
    return Path(os.getenv("BEACON_DB", "/data/beacon.db")).parent / "beacon-updates"


def _json(path):
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, UnicodeError):
        return {}


def _atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".beacon-", dir=str(path.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(data, file)
            file.flush()
            os.fsync(file.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _status_set(state, message, **data):
    with STATUS_LOCK:
        current = _json(_root() / "status.json")
        current.update({"state": state, "message": message, "updated_at": int(time.time()), **data})
        _atomic_json(_root() / "status.json", current)


def _github_get(url, *, max_bytes=2 * 1024 * 1024):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in VALID_HOSTS:
        raise ValueError("Refusing an update download outside official GitHub")
    request = URLRequest(url, headers={
        "Accept": "application/vnd.github+json" if parsed.hostname == "api.github.com" else "application/octet-stream",
        "User-Agent": "Beacon-Server-Native-Updater",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with build_opener(SafeGitHubRedirects()).open(request, timeout=25) as response:
        payload = response.read(max_bytes + 1)
        if len(payload) > max_bytes:
            raise ValueError("GitHub response exceeded safety limits")
        return payload


def _github_json(url, *, max_bytes=2 * 1024 * 1024):
    result = json.loads(_github_get(url, max_bytes=max_bytes))
    if not isinstance(result, dict):
        raise ValueError("Unexpected response from GitHub")
    return result


def _head():
    data = _github_json(GITHUB_API + "/commits/main")
    sha = data.get("sha")
    if not isinstance(sha, str) or not COMMIT.fullmatch(sha):
        raise ValueError("GitHub did not return a valid commit")
    return {
        "revision": sha,
        "message": str(data.get("commit", {}).get("message", "")).splitlines()[0][:180],
    }


def _git_blob_hash(content):
    return hashlib.sha1(b"blob " + str(len(content)).encode("ascii") + b"\x00" + content).hexdigest()


def _manifest(revision):
    commit = _github_json(GITHUB_API + "/git/commits/" + revision)
    tree_sha = commit.get("tree", {}).get("sha")
    if not isinstance(tree_sha, str) or not COMMIT.fullmatch(tree_sha):
        raise ValueError("GitHub commit has no valid source tree")
    tree = _github_json(GITHUB_API + "/git/trees/" + tree_sha + "?recursive=1", max_bytes=8 * 1024 * 1024)
    if tree.get("truncated"):
        raise ValueError("GitHub source tree was truncated; installation refused")
    blobs = {}
    for item in tree.get("tree", []):
        name = item.get("path")
        if isinstance(name, str) and item.get("type") == "blob":
            blobs[name] = item.get("sha")
    if not blobs.get("server/main.py") or not blobs.get("server/update_control.py") or not blobs.get("server/static/index.html"):
        raise ValueError("Commit does not contain a complete Beacon server")
    return blobs


def _install_archive(data, sha, blobs, target):
    count = 0
    total = 0
    found = set()
    requirements = None
    version = None
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        for member in archive:
            parts = PurePosixPath(member.name).parts
            if not parts or len(parts) < 2:
                continue
            # GitHub archives have exactly one root directory. Never follow
            # symlinks, hardlinks, devices or paths containing traversal.
            if member.issym() or member.islnk() or member.isdev():
                raise ValueError("Update archive contains an unsafe file type")
            if ".." in parts or any(part in (".", "") for part in parts):
                raise ValueError("Update archive contains an invalid path")
            relative = "/".join(parts[1:])
            if member.isdir():
                continue
            if not member.isfile():
                raise ValueError("Unexpected archive entry")
            if relative != "requirements.txt" and not relative.startswith("server/"):
                continue
            count += 1
            if count > MAX_FILES or member.size > 4 * 1024 * 1024:
                raise ValueError("Update has too many files or an oversized file")
            total += member.size
            if total > MAX_TOTAL_EXTRACTED:
                raise ValueError("Update expands beyond allowed size")
            if relative in found or not isinstance(blobs.get(relative), str):
                raise ValueError("Duplicate or untracked application file: " + relative)
            found.add(relative)
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError("Cannot extract Beacon application source")
            source = stream.read(member.size + 1)
            if len(source) != member.size or _git_blob_hash(source) != blobs[relative]:
                raise ValueError("Git blob integrity check failed: " + relative)
            if relative == "requirements.txt":
                requirements = source
                continue
            if relative == "server/version.txt":
                version = source.decode("ascii").strip()
            if not relative.endswith((".py", ".html", ".css", ".js", ".json", ".png",
                                      ".jpg", ".jpeg", ".webp", ".svg", ".ico", ".txt", ".woff2")):
                raise ValueError("Unrecognized server package file: " + relative)
            target_path = target.joinpath(*PurePosixPath(relative).parts)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            if relative.endswith(".py"):
                compile(source, relative, "exec")
            target_path.write_bytes(source)
    installed_requirements = Path("/app/requirements.txt").read_bytes()
    if requirements is None or requirements != installed_requirements:
        raise ValueError("This release changes Python dependencies. A Docker image rebuild is required.")
    if not {"server/main.py", "server/update_control.py", "server/static/index.html", "server/__init__.py"}.issubset(found):
        raise ValueError("Incomplete server release. Existing installation preserved.")
    if not version or not re.fullmatch(r"[0-9A-Za-z][0-9A-Za-z.+_-]{0,31}", version):
        raise ValueError("The GitHub source does not include a valid server/version.txt")
    return version


def _stage(revision):
    root = _root()
    release = root / "releases" / revision
    if release.is_dir() and not release.is_symlink():
        saved = _json(release / "release.json")
        hashes = saved.get("files")
        if saved.get("revision") == revision and isinstance(hashes, dict) and hashes:
            try:
                intact = all(
                    isinstance(name, str) and name.startswith("server/") and
                    ".." not in Path(name).parts and not (release / name).is_symlink() and
                    (release / name).is_file() and
                    hashlib.sha256((release / name).read_bytes()).hexdigest() == digest
                    for name, digest in hashes.items()
                )
            except OSError:
                intact = False
            if intact and "server/main.py" in hashes:
                return saved
        # An incomplete or tampered code release may never be activated.
        # Discard only that staging directory, not any application data.
        shutil.rmtree(release)
    elif release.is_symlink():
        raise ValueError("Unsafe existing release link. Update refused.")
    _status_set("downloading", "Downloading Beacon from GitHub…", target_revision=revision)
    blobs = _manifest(revision)
    archive = _github_get(GITHUB_API + "/tarball/" + revision, max_bytes=MAX_TARBALL)
    digest = hashlib.sha256(archive).hexdigest()
    root.joinpath("staging").mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix="beacon-", dir=str(root / "staging")))
    try:
        _status_set("verifying", "Verifying the GitHub commit and checking source compatibility…")
        version = _install_archive(archive, revision, blobs, temp)
        staged_files = {
            str(path.relative_to(temp)).replace(os.sep, "/"):
                hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (temp / "server").rglob("*") if path.is_file()
        }
        meta = {
            "revision": revision,
            "version": version,
            "archive_sha256": digest,
            "downloaded_at": int(time.time()),
            "files": staged_files,
        }
        _atomic_json(temp / "release.json", meta)
        release.parent.mkdir(parents=True, exist_ok=True)
        if not release.exists():
            os.rename(temp, release)
        return meta
    finally:
        if temp.exists():
            shutil.rmtree(temp)


def _current_revision():
    return os.getenv("BEACON_RUNTIME_REVISION", os.getenv("BEACON_REVISION", "unknown"))


def _check():
    result = _head()
    result["current_revision"] = _current_revision()
    result["update_available"] = result["revision"] != result["current_revision"]
    result["checked_at"] = int(time.time())
    _atomic_json(_root() / "check.json", result)
    return result


def _background_install():
    root = _root()
    try:
        head = _head()
        if head["revision"] == _current_revision():
            _status_set("up_to_date", "Beacon is already running the latest GitHub commit.", target_revision=head["revision"])
            return
        meta = _stage(head["revision"])
        _status_set("activating", "Release verified. Activating; the server will reconnect automatically…",
                    target_revision=head["revision"], target_version=meta["version"])
        _atomic_json(root / "pending.json", {"revision": head["revision"]})
        # The image supervisor notices this file, gracefully restarts the app,
        # checks /health and reverts if launch or early runtime checks fail.
    except HTTPError as exc:
        _status_set("failed", "GitHub download failed (HTTP " + str(exc.code) + "). Existing server preserved.")
    except (URLError, OSError, ValueError, tarfile.TarError, SyntaxError,
            UnicodeError, json.JSONDecodeError) as exc:
        _status_set("failed", "Update was not installed: " + str(exc)[:240] + ". Existing server preserved.")
    finally:
        with STAGING_LOCK:
            (_root() / "install.lock").unlink(missing_ok=True)


def _busy():
    root = _root()
    if (root / "install.lock").exists():
        return True
    return (root / "pending.json").exists()


def _acquire():
    root = _root()
    root.mkdir(parents=True, exist_ok=True)
    with STAGING_LOCK:
        try:
            fd = os.open(root / "install.lock", os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            raise HTTPException(409, "An update is already being downloaded or installed.") from None
        else:
            os.close(fd)


def register(app, *, administrator):
    @app.get("/api/admin/update/status")
    def update_status(request: Request):
        administrator(request)
        root = _root()
        current = _current_revision()
        previous = _json(root / "current.json").get("previous") or ""
        latest = _json(root / "check.json")
        status = _json(root / "status.json")
        return {
            "configured": True,
            "provider": "github",
            "repository": REPO,
            "channel": "main",
            "current_version": app.version,
            "revision": current,
            "available": latest if latest else None,
            "state": status.get("state", "idle"),
            "message": status.get("message", "Ready to check GitHub for updates."),
            "last_failure": status.get("last_failure", ""),
            "updated_at": status.get("updated_at"),
            "busy": _busy(),
            "can_rollback": bool(previous and (root / "releases" / previous).exists())
                            or bool(previous == "" and _json(root / "current.json").get("revision")),
        }

    @app.get("/api/admin/update/check")
    def check_updates(request: Request):
        administrator(request)
        try:
            return _check()
        except (HTTPError, URLError, OSError, ValueError, TimeoutError,
                json.JSONDecodeError) as exc:
            raise HTTPException(502, "Unable to check GitHub for updates: " + str(exc)[:160]) from None

    @app.post("/api/admin/update", status_code=202)
    def install_update(request: Request, tasks: BackgroundTasks):
        administrator(request)
        if _busy():
            raise HTTPException(409, "Update is already in progress.")
        _acquire()
        try:
            _status_set("queued", "Starting GitHub release download and verification…")
            tasks.add_task(_background_install)
        except Exception:
            (_root() / "install.lock").unlink(missing_ok=True)
            raise
        return {"state": "queued", "message": "GitHub update started. Beacon will verify and restart automatically."}

    @app.post("/api/admin/update/rollback", status_code=202)
    def rollback(request: Request):
        administrator(request)
        root = _root()
        if _busy():
            raise HTTPException(409, "An update is still in progress.")
        state = _json(root / "current.json")
        previous = state.get("previous")
        if previous is None or not state.get("revision"):
            raise HTTPException(409, "No prior release is available for rollback.")
        if previous and not (root / "releases" / previous / "release.json").is_file():
            raise HTTPException(409, "Previous version files are missing.")
        _status_set("rolling_back", "Switching back to the previous server version…")
        _atomic_json(root / "pending.json", {"revision": previous})
        return {"state": "rolling_back", "message": "Rollback requested. Beacon will reconnect automatically."}
