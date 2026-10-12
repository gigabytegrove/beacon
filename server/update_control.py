"""Admin-only Dokploy Compose redeploy bridge.

The application never mounts the Docker socket or exposes Dokploy credentials
to browser clients. A request is *accepted* only when queued; the background
task records whether Dokploy accepted the redeploy request. Running the new
image is only confirmed after the replacement container passes health checks.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request as URLRequest, build_opener

from fastapi import BackgroundTasks, HTTPException, Request

_DEPLOYMENT_LOCK = threading.Lock()
_DEPLOYMENT = {"state": "idle", "requested_at": None, "message": "No update requested in this process."}
_LAST_REQUEST_MONOTONIC = 0.0
_COOLDOWN_SECONDS = 120


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Dokploy redirected the deployment API request")


def _configuration():
    origin = os.getenv("BEACON_DOKPLOY_URL", "").strip().rstrip("/")
    compose_id = os.getenv("BEACON_DOKPLOY_COMPOSE_ID", "").strip()
    api_key = os.getenv("BEACON_DOKPLOY_API_KEY", "").strip()
    if not (origin and compose_id and api_key):
        return None
    parsed = urlsplit(origin)
    if (parsed.scheme != "https" or not parsed.hostname or
            parsed.username or parsed.password or parsed.query or
            parsed.fragment or parsed.path not in ("", "/")):
        return None
    if not re.fullmatch(r"[A-Za-z0-9_-]{5,128}", compose_id):
        return None
    return origin, compose_id, api_key


def _status(version):
    with _DEPLOYMENT_LOCK:
        snapshot = dict(_DEPLOYMENT)
    return {
        "configured": _configuration() is not None,
        "current_version": version,
        "revision": os.getenv("BEACON_REVISION", "unknown"),
        "deployment_source": os.getenv("BEACON_UPDATE_CHANNEL", "git"),
        "state": snapshot["state"],
        "requested_at": snapshot["requested_at"],
        "message": snapshot["message"],
    }


def _redeploy(config):
    origin, compose_id, api_key = config
    url = origin + "/api/compose.redeploy"
    payload = json.dumps({
        "composeId": compose_id,
        "freshVolumes": False,
        "title": "Beacon administrator update",
        "description": "Requested from the Beacon server control center",
    }).encode("utf-8")
    request = URLRequest(url, data=payload, headers={
        "Content-Type": "application/json",
        "Accept": "application/json",
        "x-api-key": api_key,
    }, method="POST")
    message = "Dokploy accepted the deployment request. Check the deployment status and verify the new server version."
    state = "accepted"
    try:
        with build_opener(_RejectRedirects()).open(request, timeout=12) as response:
            if not 200 <= response.status < 300:
                raise ValueError("Dokploy did not accept the deployment request")
    except HTTPError as exc:
        state = "failed"
        message = f"Dokploy rejected the deployment request (HTTP {exc.code})."
    except (URLError, OSError, ValueError, TimeoutError):
        state = "failed"
        message = "Could not request deployment from Dokploy. Check the Dokploy URL, credentials, and network."
    with _DEPLOYMENT_LOCK:
        _DEPLOYMENT["state"] = state
        _DEPLOYMENT["message"] = message


def register(app, *, administrator):
    @app.get("/api/admin/update/status")
    def update_status(request: Request):
        administrator(request)
        return _status(app.version)

    @app.post("/api/admin/update", status_code=202)
    def request_update(request: Request, background_tasks: BackgroundTasks):
        administrator(request)
        config = _configuration()
        if config is None:
            raise HTTPException(
                503, "Server updater is not configured. Set the Dokploy URL, Compose ID and API key on the server."
            )
        global _LAST_REQUEST_MONOTONIC
        with _DEPLOYMENT_LOCK:
            now = time.monotonic()
            if now - _LAST_REQUEST_MONOTONIC < _COOLDOWN_SECONDS:
                raise HTTPException(429, "Another update was requested recently. Check its status before retrying.")
            _LAST_REQUEST_MONOTONIC = now
            _DEPLOYMENT.update({
                "state": "queued",
                "requested_at": int(time.time()),
                "message": "Request queued. Dokploy has not yet confirmed it.",
            })
        background_tasks.add_task(_redeploy, config)
        return {"state": "queued", "message": "Deployment request queued; this does not confirm an update was installed."}
