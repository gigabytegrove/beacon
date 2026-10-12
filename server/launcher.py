"""Portable in-container supervisor for Beacon's native GitHub updater.

The supervisor is included in the Docker image once. Application code runs
from either the image or versioned directories in the existing /data volume.
No container-engine socket, orchestrator API, sidecar or root privilege needed.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

DATA = Path(os.getenv("BEACON_DB", "/data/beacon.db")).parent / "beacon-updates"
BASE = Path("/app")
stop_requested = False
child = None


def _read(path):
    try:
        with path.open("r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".new")
    with temp.open("w", encoding="utf-8") as out:
        json.dump(data, out)
        out.flush()
        os.fsync(out.fileno())
    os.replace(temp, path)


def _release(sha):
    if not isinstance(sha, str) or len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
        return None
    folder = DATA / "releases" / sha
    if not (folder / "server" / "main.py").is_file() or not (folder / "release.json").is_file():
        return None
    meta = _read(folder / "release.json")
    if meta.get("revision") != sha:
        return None
    files = meta.get("files")
    if not isinstance(files, dict) or not files or "server/main.py" not in files:
        return None
    try:
        for name, digest in files.items():
            if not isinstance(name, str) or not name.startswith("server/") or not isinstance(digest, str):
                return None
            path = folder / name
            if ".." in Path(name).parts or path.is_symlink() or not path.is_file():
                return None
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                return None
    except OSError:
        return None
    return folder


def _running(sha):
    global child
    folder = _release(sha) if sha else None
    if sha and folder is None:
        return None
    root = folder if folder else BASE
    meta = _read(root / "release.json") if sha else {}
    env = os.environ.copy()
    if sha:
        env["BEACON_RUNTIME_REVISION"] = sha
        env["BEACON_RUNTIME_VERSION"] = str(meta.get("version") or env.get("BEACON_VERSION") or "unknown")
    else:
        env["BEACON_RUNTIME_REVISION"] = env.get("BEACON_REVISION", "image")
        env["BEACON_RUNTIME_VERSION"] = env.get("BEACON_VERSION", "unknown")
    # cwd is the import root: uvicorn imports the complete release package,
    # not the image copy in /app/server.
    child = subprocess.Popen([
        sys.executable, "-m", "uvicorn", "server.main:app",
        "--host", "0.0.0.0", "--port", "8765", "--no-proxy-headers",
    ], cwd=str(root), env=env)
    return child


def _healthy(process, revision, deadline=35):
    until = time.monotonic() + deadline
    while not stop_requested and time.monotonic() < until:
        if process.poll() is not None:
            return False
        try:
            with urlopen("http://127.0.0.1:8765/health", timeout=1) as response:
                if response.status == 200:
                    info = json.load(response)
                    if info.get("status") == "ok" and info.get("revision") == revision:
                        return True
        except (OSError, URLError, ValueError, TimeoutError):
            pass
        time.sleep(0.4)
    return False


def _stop_child():
    global child
    if child is None or child.poll() is not None:
        return
    child.terminate()
    try:
        child.wait(timeout=12)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait(timeout=5)


def _signal(_sig, _frame):
    global stop_requested
    stop_requested = True
    _stop_child()


def _prune(keep_active="", keep_previous="", keep_count=3):
    """Keep a few rollback points without growing the persistent volume forever."""
    directory = DATA / "releases"
    if not directory.exists():
        return
    all_releases = []
    for entry in directory.iterdir():
        if entry.is_symlink() or not entry.is_dir():
            continue
        if len(entry.name) != 40 or any(c not in "0123456789abcdef" for c in entry.name):
            continue
        if _release(entry.name):
            all_releases.append(entry)
    all_releases.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    retained = {keep_active, keep_previous}
    retained.update(path.name for path in all_releases[:max(keep_count, 2)])
    for release in all_releases:
        if release.name not in retained:
            try:
                shutil.rmtree(release)
            except OSError as error:
                print("Beacon: could not prune old release: " + str(error), flush=True)


def _version(sha):
    if not sha:
        return os.getenv("BEACON_VERSION", "image")
    return _read(DATA / "releases" / sha / "release.json").get("version", "unknown")


def main():
    global child
    signal.signal(signal.SIGTERM, _signal)
    signal.signal(signal.SIGINT, _signal)
    DATA.mkdir(parents=True, exist_ok=True)
    # An update job killed during download must not block all future attempts.
    (DATA / "install.lock").unlink(missing_ok=True)
    active_file = DATA / "current.json"
    pending_file = DATA / "pending.json"
    active = _read(active_file).get("revision") or ""
    if active and _release(active) is None:
        print("Beacon: stored active release is invalid; falling back to image", flush=True)
        active = ""
        _write(active_file, {"revision": "", "previous": ""})
    failures = 0
    probation_until = 0.0
    while not stop_requested:
        selected = active
        proc = _running(selected)
        if proc is None:
            selected = ""
            active = ""
            proc = _running("")
        expected = selected or os.getenv("BEACON_REVISION", "image")
        if not _healthy(proc, expected):
            print("Beacon: launch health check failed for " + (selected or "image"), flush=True)
            _stop_child()
            if selected:
                state = _read(active_file)
                fallback = state.get("previous") or ""
                active = fallback if _release(fallback) else ""
                _write(active_file, {"revision": active, "previous": ""})
                _write(DATA / "status.json", {
                    "state": "rolled_back",
                    "message": "New version failed its startup health check. Previous version restored.",
                    "last_failure": "Startup health check failed for " + selected,
                    "revision": active,
                })
                continue
            failures += 1
            if failures >= 3:
                print("Beacon: image failed three launch attempts; exiting", flush=True)
                return 1
            time.sleep(2)
            continue
        failures = 0
        print("Beacon: healthy version=" + _version(selected) + " revision=" + (selected or "image"), flush=True)
        prior_status = _read(DATA / "status.json")
        _write(DATA / "status.json", {
            "state": "running", "message": "Server healthy.",
            "revision": selected or expected,
            "last_failure": prior_status.get("last_failure", ""),
        })
        previous = _read(active_file).get("previous") or ""
        _prune(selected, previous)
        probation_until = time.monotonic() + 60
        switching = False
        while not stop_requested and proc.poll() is None:
            pending = _read(pending_file)
            requested = pending.get("revision")
            if pending and (requested == "" or _release(requested)):
                pending_file.unlink(missing_ok=True)
                if requested != selected:
                    switching = True
                    active = requested
                    _write(active_file, {"revision": active, "previous": selected})
                    print("Beacon: activating " + (active or "image"), flush=True)
                    _stop_child()
                    break
            time.sleep(0.5)
        if stop_requested:
            break
        if switching:
            continue
        # Exit shortly after installation signals a broken release. Restore
        # previous code rather than endlessly restarting the bad candidate.
        if selected and time.monotonic() < probation_until:
            state = _read(active_file)
            previous = state.get("previous") or ""
            active = previous if _release(previous) else ""
            _write(active_file, {"revision": active, "previous": ""})
            _write(DATA / "status.json", {
                "state": "rolled_back",
                "message": "Updated server exited during its health probation. Previous version restored.",
                "last_failure": "Updated server exited during the health probation: " + selected,
                "revision": active,
            })
        else:
            time.sleep(2)
    _stop_child()
    return 0


if __name__ == "__main__":
    sys.exit(main())
