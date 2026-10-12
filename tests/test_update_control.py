"""No live Dokploy connection is used in these tests."""
from __future__ import annotations

import importlib
import json
from contextlib import nullcontext

from fastapi.testclient import TestClient


def _app(monkeypatch, tmp_path):
    monkeypatch.setenv("BEACON_DB", str(tmp_path / "beacon.db"))
    monkeypatch.setenv("BEACON_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("BEACON_ADMIN_PASSWORD", "correct horse battery staple")
    for key in ("BEACON_DOKPLOY_URL", "BEACON_DOKPLOY_COMPOSE_ID", "BEACON_DOKPLOY_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    import server.main as main
    import server.update_control as updater
    updater = importlib.reload(updater)
    main = importlib.reload(main)
    return main, updater


def _admin(client):
    response = client.post("/api/login", json={
        "username": "admin", "password": "correct horse battery staple",
        "device_name": "Browser",
    })
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["token"]}


def test_update_status_is_admin_only_and_disabled_without_credentials(monkeypatch, tmp_path):
    main, _ = _app(monkeypatch, tmp_path)
    with TestClient(main.app) as client:
        auth = _admin(client)
        assert client.get("/api/admin/update/status").status_code == 401
        response = client.get("/api/admin/update/status", headers=auth)
        assert response.status_code == 200
        data = response.json()
        assert data["configured"] is False
        assert data["state"] == "idle"
        assert "api_key" not in data
        assert client.post("/api/admin/update", headers=auth).status_code == 503
        created = client.post("/api/admin/users", headers=auth, json={
            "username": "member", "password": "member secure pass",
            "display_name": "Member",
        })
        assert created.status_code == 201
        login = client.post("/api/login", json={
            "username": "member", "password": "member secure pass",
            "device_name": "Mobile",
        })
        member = {"Authorization": "Bearer " + login.json()["token"]}
        assert client.get("/api/admin/update/status", headers=member).status_code == 403
        assert client.post("/api/admin/update", headers=member).status_code == 403


def test_dokploy_redeploy_authentication_cooldown_and_volume_safety(monkeypatch, tmp_path):
    main, updater = _app(monkeypatch, tmp_path)
    monkeypatch.setenv("BEACON_DOKPLOY_URL", "https://dokploy.example.test")
    monkeypatch.setenv("BEACON_DOKPLOY_COMPOSE_ID", "compose123")
    monkeypatch.setenv("BEACON_DOKPLOY_API_KEY", "fake-local-test-key")
    seen = []

    class Response:
        status = 200
        def read(self, size=1048576):
            return b"{}"

    class Opener:
        def open(self, req, timeout):
            seen.append({
                "url": req.full_url,
                "headers": dict(req.header_items()),
                "body": json.loads(req.data),
                "timeout": timeout,
                "method": req.get_method(),
            })
            return nullcontext(Response())

    monkeypatch.setattr(updater, "build_opener", lambda *_: Opener())
    with TestClient(main.app) as client:
        auth = _admin(client)
        assert client.post("/api/admin/update").status_code == 401
        requested = client.post("/api/admin/update", headers=auth)
        assert requested.status_code == 202, requested.text
        assert requested.json()["state"] == "queued"
        assert len(seen) == 1
        assert seen[0]["url"] == "https://dokploy.example.test/api/compose.redeploy"
        assert seen[0]["method"] == "POST"
        assert seen[0]["headers"]["X-api-key"] == "fake-local-test-key"
        assert seen[0]["body"]["composeId"] == "compose123"
        assert seen[0]["body"]["freshVolumes"] is False
        assert seen[0]["timeout"] == 12
        status = client.get("/api/admin/update/status", headers=auth).json()
        assert status["state"] == "accepted"
        assert "fake-local-test-key" not in json.dumps(status)
        assert client.post("/api/admin/update", headers=auth).status_code == 429


def test_insecure_or_invalid_dokploy_url_is_disabled(monkeypatch, tmp_path):
    main, _ = _app(monkeypatch, tmp_path)
    monkeypatch.setenv("BEACON_DOKPLOY_COMPOSE_ID", "compose123")
    monkeypatch.setenv("BEACON_DOKPLOY_API_KEY", "fake-local-test-key")
    with TestClient(main.app) as client:
        auth = _admin(client)
        for url in (
            "http://dokploy.example.test", "https://user:pass@dokploy.example.test",
            "https://dokploy.example.test/other/path",
            "https://dokploy.example.test?secret=1",
        ):
            monkeypatch.setenv("BEACON_DOKPLOY_URL", url)
            assert client.get("/api/admin/update/status", headers=auth).json()["configured"] is False
            assert client.post("/api/admin/update", headers=auth).status_code == 503
