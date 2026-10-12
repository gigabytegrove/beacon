"""Administrator-only in-app updater for Dokploy-hosted Beacon.

The existing Dokploy installation performs deployments. Beacon needs no Docker
socket, privileged container, sidecar or CI workflow. Dokploy credentials are
stored exclusively in a 0600 file beside the persistent Beacon database; they
are never returned by the configuration, status or update APIs.
"""
from __future__ import annotations

import json
import os
import re
import stat
import tempfile
import threading
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request as URLRequest, build_opener

from fastapi import BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, Field

_DEPLOYMENT_LOCK = threading.Lock()
_DEPLOYMENT = {
    "state": "idle",
    "requested_at": None,
    "message": "No update requested in this server process.",
}
_LAST_REQUEST_MONOTONIC = 0.0
_COOLDOWN_SECONDS = 120
_CONFIG_LOCK = threading.RLock()


class DokploySetup(BaseModel):
    url: str = Field(min_length=9, max_length=512)
    compose_id: str = Field(min_length=1, max_length=128)
    # Empty string retains the previously saved or environment-provided key.
    api_key: str = Field(default="", max_length=2048)


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Dokploy redirected the deployment API request")


def _settings_path() -> Path:
    return Path(os.getenv("BEACON_DB", "/data/beacon.db") + ".updater.json")


def _read_saved() -> dict:
    path = _settings_path()
    try:
        metadata = path.lstat()
        if (not stat.S_ISREG(metadata.st_mode) or
                metadata.st_uid != os.getuid() or
                metadata.st_mode & 0o077):
            # Never use a symlink or a secret readable by another account.
            return {}
        with path.open("r", encoding="utf-8") as file:
            raw = json.load(file)
        return raw if isinstance(raw, dict) else {}
    except (OSError, ValueError, UnicodeError, TypeError):
        return {}


def _environment_config() -> dict:
    return {
        "url": os.getenv("BEACON_DOKPLOY_URL", "").strip(),
        "compose_id": os.getenv("BEACON_DOKPLOY_COMPOSE_ID", "").strip(),
        "api_key": os.getenv("BEACON_DOKPLOY_API_KEY", "").strip(),
    }


def _validated(config: dict):
    url = str(config.get("url", "")).strip().rstrip("/")
    compose_id = str(config.get("compose_id", "")).strip()
    api_key = str(config.get("api_key", "")).strip()
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or
            parsed.username or parsed.password or parsed.query or
            parsed.fragment or parsed.path not in ("", "/") or
            any(ch.isspace() for ch in url)):
        raise ValueError("Enter your Dokploy HTTPS address (for example, https://dokploy.example.com).")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Dokploy URL has an invalid port.") from exc
    if port == 0 or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", compose_id):
        raise ValueError("Enter the Compose service ID from Dokploy, not its display name.")
    if not api_key:
        raise ValueError("Enter a Dokploy API key authorized to deploy this Compose service.")
    return url, compose_id, api_key


def _configuration():
    with _CONFIG_LOCK:
        saved = _read_saved()
        env = _environment_config()
        for source, values in (("saved", saved), ("environment", env)):
            try:
                return _validated(values)
            except ValueError:
                pass
    return None


def _configuration_summary():
    with _CONFIG_LOCK:
        saved = _read_saved()
        env = _environment_config()
        for source, values in (("saved", saved), ("environment", env)):
            try:
                url, compose_id, _ = _validated(values)
                return {
                    "configured": True,
                    "source": source,
                    "url": url,
                    "compose_id": compose_id,
                    "api_key_present": True,
                }
            except ValueError:
                pass
    return {
        "configured": False,
        "source": "none",
        "url": "",
        "compose_id": "",
        "api_key_present": False,
    }


def _write_saved(config: dict):
    path = _settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".beacon-updater-", dir=str(path.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(config, file, separators=(",", ":"))
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
        # The file must stay accessible to the non-root Beacon user alone.
        path.chmod(0o600)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _request(config, endpoint: str, *, payload=None, query=None):
    origin, compose_id, api_key = config
    url = origin + "/api/" + endpoint
    if query:
        url += "?" + urlencode(query)
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "x-api-key": api_key,
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = URLRequest(url, data=body, headers=headers, method="POST" if body is not None else "GET")
    with build_opener(_RejectRedirects()).open(request, timeout=12) as response:
        if not 200 <= response.status < 300:
            raise ValueError("Dokploy API request did not succeed")
        return response.read(1048576)


def _verify_dokploy(config):
    try:
        _request(config, "compose.one", query={"composeId": config[1]})
    except HTTPError as exc:
        if exc.code in (401, 403):
            raise HTTPException(422, "Dokploy rejected the API key or does not allow access to this Compose service.") from None
        if exc.code == 404:
            raise HTTPException(422, "Dokploy could not find that Compose service ID.") from None
        raise HTTPException(502, f"Dokploy configuration check failed (HTTP {exc.code}).") from None
    except (URLError, OSError, ValueError, TimeoutError):
        raise HTTPException(502, "Could not reach Dokploy securely. Check its HTTPS URL, TLS certificate and network access.") from None


def _status(version):
    with _DEPLOYMENT_LOCK:
        snapshot = dict(_DEPLOYMENT)
    return {
        "configured": _configuration() is not None,
        "configuration_source": _configuration_summary()["source"],
        "current_version": version,
        "revision": os.getenv("BEACON_REVISION", "unknown"),
        "deployment_source": os.getenv("BEACON_UPDATE_CHANNEL", "git"),
        "state": snapshot["state"],
        "requested_at": snapshot["requested_at"],
        "message": snapshot["message"],
    }


def _redeploy(config):
    message = "Dokploy accepted the deployment request. Beacon may briefly disconnect as the server is replaced."
    state = "accepted"
    try:
        _request(config, "compose.redeploy", payload={
            "composeId": config[1],
            "freshVolumes": False,
            "title": "Beacon update from Control Center",
            "description": "Requested by a Beacon server administrator",
        })
    except HTTPError as exc:
        state = "failed"
        message = f"Dokploy rejected the deployment request (HTTP {exc.code}). Check the Compose ID and API-key permissions."
    except (URLError, OSError, ValueError, TimeoutError):
        state = "failed"
        message = "Could not request a deployment from Dokploy. Check its URL, TLS certificate and network."
    with _DEPLOYMENT_LOCK:
        _DEPLOYMENT.update({"state": state, "message": message})


def register(app, *, administrator):
    @app.get("/api/admin/update/config")
    def get_update_config(request: Request):
        administrator(request)
        return _configuration_summary()

    @app.put("/api/admin/update/config")
    def save_update_config(data: DokploySetup, request: Request):
        administrator(request)
        with _CONFIG_LOCK:
            key = data.api_key.strip()
            if not key:
                existing = _configuration()
                if existing:
                    # Never forward an already stored API key to a newly
                    # entered host. Changing Dokploy servers requires a fresh
                    # key to prevent credential exfiltration via this API.
                    requested_origin = data.url.strip().rstrip("/")
                    if requested_origin != existing[0]:
                        raise HTTPException(422, "Changing Dokploy addresses requires entering a new API key.")
                    key = existing[2]
            try:
                config = _validated({
                    "url": data.url, "compose_id": data.compose_id, "api_key": key,
                })
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from None
            # Verify the key can read this exact service before saving. No deploy.
            _verify_dokploy(config)
            try:
                _write_saved({"url": config[0], "compose_id": config[1], "api_key": config[2]})
            except OSError:
                raise HTTPException(500, "Could not save updater settings in Beacon's persistent data directory.") from None
        return {**_configuration_summary(), "message": "Dokploy connection verified and saved. Future updates are available here."}

    @app.delete("/api/admin/update/config")
    def disconnect_update_config(request: Request):
        administrator(request)
        with _CONFIG_LOCK:
            try:
                _settings_path().unlink(missing_ok=True)
            except OSError:
                raise HTTPException(500, "Could not remove the saved Dokploy connection.") from None
        return _configuration_summary()

    @app.get("/api/admin/update/status")
    def update_status(request: Request):
        administrator(request)
        return _status(app.version)

    @app.post("/api/admin/update", status_code=202)
    def request_update(request: Request, background_tasks: BackgroundTasks):
        administrator(request)
        config = _configuration()
        if config is None:
            raise HTTPException(503, "Connect Beacon to your Dokploy Compose service on the Updates page first.")
        global _LAST_REQUEST_MONOTONIC
        with _DEPLOYMENT_LOCK:
            now = time.monotonic()
            if now - _LAST_REQUEST_MONOTONIC < _COOLDOWN_SECONDS:
                raise HTTPException(429, "An update was requested recently. Check its status before retrying.")
            _LAST_REQUEST_MONOTONIC = now
            _DEPLOYMENT.update({
                "state": "queued", "requested_at": int(time.time()),
                "message": "Request queued. Dokploy has not yet accepted it.",
            })
        background_tasks.add_task(_redeploy, config)
        return {
            "state": "queued",
            "message": "Dokploy update requested. The existing database volume will be retained.",
        }
