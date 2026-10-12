"""Self-service in-app Dokploy updater tests. No external network or Docker."""
import importlib
import json
import stat

from fastapi import HTTPException
from fastapi.testclient import TestClient


def _setup(monkeypatch, tmp_path):
    monkeypatch.setenv("BEACON_DB", str(tmp_path / "beacon.db"))
    monkeypatch.setenv("BEACON_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("BEACON_ADMIN_PASSWORD", "correct horse battery staple")
    for key in ("BEACON_DOKPLOY_URL", "BEACON_DOKPLOY_COMPOSE_ID", "BEACON_DOKPLOY_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    import server.update_control as updater
    import server.main as main
    updater = importlib.reload(updater)
    main = importlib.reload(main)
    return main, updater


def _login(client, username="admin", password="correct horse battery staple"):
    response = client.post("/api/login", json={
        "username": username, "password": password, "device_name": "Browser",
    })
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["token"]}


def test_save_connection_inside_ui_and_update_without_compose_changes(monkeypatch, tmp_path):
    main, updater = _setup(monkeypatch, tmp_path)
    validated = []
    monkeypatch.setattr(updater, "_verify_dokploy", lambda config: validated.append(config))
    with TestClient(main.app) as client:
        auth = _login(client)
        assert client.get("/api/admin/update/config").status_code == 401
        initial = client.get("/api/admin/update/config", headers=auth).json()
        assert initial["configured"] is False

        payload = {
            "url": "https://dokploy.example.test",
            "compose_id": "compose123",
            "api_key": "nonproduction-fixture-secret",
        }
        response = client.put("/api/admin/update/config", headers=auth, json=payload)
        assert response.status_code == 200, response.text
        assert validated == [(
            "https://dokploy.example.test", "compose123",
            "nonproduction-fixture-secret",
        )]
        assert response.json()["configured"] is True
        assert response.json()["source"] == "saved"
        assert "api_key" not in response.json()
        assert "nonproduction-fixture-secret" not in response.text
        assert client.get("/api/admin/update/status", headers=auth).json()["configured"] is True

        secret_file = tmp_path / "beacon.db.updater.json"
        assert secret_file.is_file()
        assert stat.S_IMODE(secret_file.stat().st_mode) == 0o600
        stored = json.loads(secret_file.read_text())
        assert stored == payload

        # Keeping the existing key does not require pasting it each time.
        modified = client.put("/api/admin/update/config", headers=auth, json={
            "url": "https://dokploy.example.test",
            "compose_id": "compose456", "api_key": "",
        })
        assert modified.status_code == 200
        assert validated[-1][1] == "compose456"
        assert validated[-1][2] == "nonproduction-fixture-secret"

        # Configuration is loaded from the same persistent volume after a
        # simulated new server import/restart.
        updater = importlib.reload(updater)
        assert updater._configuration() == (
            "https://dokploy.example.test", "compose456",
            "nonproduction-fixture-secret",
        )
        assert "nonproduction-fixture-secret" not in json.dumps(updater._configuration_summary())

        removed = client.delete("/api/admin/update/config", headers=auth)
        assert removed.status_code == 200
        assert removed.json()["configured"] is False
        assert not secret_file.exists()


def test_invalid_url_and_failed_verification_never_replace_saved_key(monkeypatch, tmp_path):
    main, updater = _setup(monkeypatch, tmp_path)
    with TestClient(main.app) as client:
        auth = _login(client)
        base = {
            "url": "https://dokploy.example.test",
            "compose_id": "compose123",
            "api_key": "nonproduction-fixture-secret",
        }
        monkeypatch.setattr(updater, "_verify_dokploy", lambda config: None)
        assert client.put("/api/admin/update/config", headers=auth, json=base).status_code == 200
        file = tmp_path / "beacon.db.updater.json"
        original = file.read_text()

        for url in (
            "http://dokploy.example.test", "https://user:pass@dokploy.example.test",
            "https://dokploy.example.test/other", "https://dokploy.example.test/?key=1",
        ):
            response = client.put("/api/admin/update/config", headers=auth, json={
                **base, "url": url,
            })
            assert response.status_code == 422, (url, response.text)
            assert file.read_text() == original

        def reject(_):
            raise HTTPException(422, "Invalid Dokploy API key.")
        monkeypatch.setattr(updater, "_verify_dokploy", reject)
        response = client.put("/api/admin/update/config", headers=auth, json={
            **base, "api_key": "incorrect-key",
        })
        assert response.status_code == 422
        assert file.read_text() == original


def test_only_admin_can_manage_connection(monkeypatch, tmp_path):
    main, updater = _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(updater, "_verify_dokploy", lambda config: None)
    payload = {
        "url": "https://dokploy.example.test",
        "compose_id": "compose123",
        "api_key": "nonproduction-fixture-secret",
    }
    with TestClient(main.app) as client:
        auth = _login(client)
        created = client.post("/api/admin/users", headers=auth, json={
            "username": "member", "password": "long valid password",
            "display_name": "Member",
        })
        assert created.status_code == 201
        member = _login(client, "member", "long valid password")
        for method, path, data in (
            ("GET", "/api/admin/update/config", None),
            ("PUT", "/api/admin/update/config", payload),
            ("DELETE", "/api/admin/update/config", None),
            ("POST", "/api/admin/update", None),
        ):
            response = client.request(method, path, headers=member, json=data)
            assert response.status_code == 403, (method, path, response.text)
        assert client.get("/api/admin/update/config", headers=auth).json()["configured"] is False


def test_saved_permissions_must_restrict_other_users(monkeypatch, tmp_path):
    main, updater = _setup(monkeypatch, tmp_path)
    file = tmp_path / "beacon.db.updater.json"
    file.write_text(json.dumps({
        "url": "https://dokploy.example.test",
        "compose_id": "compose123",
        "api_key": "incorrectly-permissioned",
    }))
    file.chmod(0o644)
    assert updater._configuration() is None
    with TestClient(main.app) as client:
        admin = _login(client)
        assert client.get("/api/admin/update/config", headers=admin).json()["configured"] is False
