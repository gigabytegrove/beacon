"""First-run admin setup must be secure, one-use, and backwards-compatible."""
import importlib
import os

from fastapi.testclient import TestClient


def fresh_server(monkeypatch, tmp_path, password=None):
    monkeypatch.setenv("BEACON_DB", str(tmp_path / "beacon.db"))
    monkeypatch.setenv("BEACON_ADMIN_USERNAME", "admin")
    if password is None:
        monkeypatch.delenv("BEACON_ADMIN_PASSWORD", raising=False)
    else:
        monkeypatch.setenv("BEACON_ADMIN_PASSWORD", password)
    import server.main as main
    return importlib.reload(main)


def test_new_install_has_wizard_and_one_time_setup_code(monkeypatch, tmp_path):
    main = fresh_server(monkeypatch, tmp_path)
    from server.bootstrap import code_path
    with TestClient(main.app) as client:
        status = client.get("/api/setup/status")
        assert status.status_code == 200
        assert status.json() == {"setup_required": True}
        code = code_path(main.DB).read_text().strip()
        assert len(code) >= 32
        assert code not in status.text
        assert client.post("/api/login", json={
            "username": "admin", "password": "not yet available",
            "device_name": "Test"
        }).status_code == 401
        wrong = client.post("/api/setup", json={
            "setup_code": "wrong-code-1234567890", "username": "owner",
            "display_name": "Owner", "password": "correct horse battery staple"
        })
        assert wrong.status_code == 403
        invalid = client.post("/api/setup", json={
            "setup_code": code, "username": "owner",
            "display_name": "Owner", "password": "short"
        })
        assert invalid.status_code == 422
        accepted = client.post("/api/setup", json={
            "setup_code": code, "username": "owner",
            "display_name": "Beacon Owner", "password": "correct horse battery staple"
        })
        assert accepted.status_code == 201, accepted.text
        assert accepted.json()["username"] == "owner"
        assert not code_path(main.DB).exists()
        assert client.get("/api/setup/status").json() == {"setup_required": False}
        assert client.post("/api/setup", json={
            "setup_code": code, "username": "hacker",
            "display_name": "Hacker", "password": "correct horse battery staple"
        }).status_code == 409
        login = client.post("/api/login", json={
            "username": "owner", "password": "correct horse battery staple",
            "device_name": "Test desktop"
        })
        assert login.status_code == 200, login.text
        assert login.json()["user"]["is_admin"] is True
    # Reboots must retain admin and never create another setup code.
    main = fresh_server(monkeypatch, tmp_path)
    with TestClient(main.app) as client:
        assert client.get("/api/setup/status").json()["setup_required"] is False
        assert not code_path(main.DB).exists()


def test_setup_code_survives_restart_until_claimed(monkeypatch, tmp_path):
    main = fresh_server(monkeypatch, tmp_path)
    from server.bootstrap import code_path
    with TestClient(main.app):
        original = code_path(main.DB).read_text()
    main = fresh_server(monkeypatch, tmp_path)
    with TestClient(main.app):
        assert code_path(main.DB).read_text() == original


def test_setup_attempt_limit_rejects_even_correct_code(monkeypatch, tmp_path):
    main = fresh_server(monkeypatch, tmp_path)
    from server.bootstrap import code_path
    with TestClient(main.app) as client:
        code = code_path(main.DB).read_text().strip()
        body = {"setup_code": "bad-code-with-enough-length", "username": "admin",
                "display_name": "Admin", "password": "correct horse battery staple"}
        for _ in range(5):
            assert client.post("/api/setup", json=body).status_code == 403
        body["setup_code"] = code
        assert client.post("/api/setup", json=body).status_code == 429


def test_legacy_explicit_admin_password_still_bootstraps(monkeypatch, tmp_path):
    main = fresh_server(monkeypatch, tmp_path, password="an existing strong password")
    from server.bootstrap import code_path
    with TestClient(main.app) as client:
        assert client.get("/api/setup/status").json() == {"setup_required": False}
        assert not code_path(main.DB).exists()
        response = client.post("/api/login", json={
            "username": "admin", "password": "an existing strong password",
            "device_name": "Test"
        })
        assert response.status_code == 200, response.text
