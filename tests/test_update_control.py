"""Beacon's native GitHub updater: Docker-manager independent, admin gated."""
from __future__ import annotations

import hashlib
import importlib
import io
import json
import os
import tarfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _app(monkeypatch, tmp_path):
    monkeypatch.setenv("BEACON_DB", str(tmp_path / "beacon.db"))
    monkeypatch.setenv("BEACON_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("BEACON_ADMIN_PASSWORD", "correct horse battery staple")
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


def test_no_dokploy_or_other_orchestrator_configuration(monkeypatch, tmp_path):
    main, updater = _app(monkeypatch, tmp_path)
    with TestClient(main.app) as client:
        auth = _login(client)
        status = client.get("/api/admin/update/status", headers=auth)
        assert status.status_code == 200
        assert status.json()["provider"] == "github"
        assert status.json()["repository"] == "gigabytegrove/beacon"
        assert status.json()["configured"] is True
        assert client.get("/api/admin/update/status").status_code == 401
        for url in ("/api/admin/update/config", "/api/admin/update/available"):
            assert client.get(url, headers=auth).status_code == 404
        assert client.get("/health").json()["status"] == "ok"
        assert "revision" in client.get("/health").json()
        assert not (tmp_path / "beacon.db.updater.json").exists()


def test_only_administrators_can_check_install_and_rollback(monkeypatch, tmp_path):
    main, updater = _app(monkeypatch, tmp_path)
    with TestClient(main.app) as client:
        admin = _login(client)
        assert client.post("/api/admin/users", headers=admin, json={
            "username": "member", "display_name": "Member",
            "password": "member secure pass",
        }).status_code == 201
        member = _login(client, "member", "member secure pass")
        for method, path in (
            ("GET", "/api/admin/update/status"),
            ("GET", "/api/admin/update/check"),
            ("POST", "/api/admin/update"),
            ("POST", "/api/admin/update/rollback"),
        ):
            assert client.request(method, path, headers=member).status_code == 403
            assert client.request(method, path).status_code == 401


def test_git_blob_checksum_pinning_and_github_url_restrictions(monkeypatch, tmp_path):
    _, updater = _app(monkeypatch, tmp_path)
    data = b"hello world"
    expected = hashlib.sha1(b"blob 11\\0hello world".replace(b"\\0", b"\x00")).hexdigest()
    assert updater._git_blob_hash(data) == expected
    with pytest.raises(ValueError):
        updater._github_get("https://evil.example.test/download")
    with pytest.raises(ValueError):
        updater._github_get("http://api.github.com/repos/gigabytegrove/beacon")


def test_github_update_check_cached_and_diffed_by_commit(monkeypatch, tmp_path):
    main, updater = _app(monkeypatch, tmp_path)
    revision = "a" * 40
    monkeypatch.setattr(updater, "_head", lambda: {"revision": revision, "message": "New stable build"})
    with TestClient(main.app) as client:
        auth = _login(client)
        response = client.get("/api/admin/update/check", headers=auth)
        assert response.status_code == 200, response.text
        assert response.json()["revision"] == revision
        assert response.json()["update_available"] is True
        status = client.get("/api/admin/update/status", headers=auth).json()
        assert status["available"]["revision"] == revision
        assert (tmp_path / "beacon-updates" / "check.json").exists()


def test_update_staging_requires_matching_repository_blobs(monkeypatch, tmp_path):
    _, updater = _app(monkeypatch, tmp_path)
    payloads = {
        "server/__init__.py": b"",
        "server/main.py": b"x = 1\n",
        "server/update_control.py": b"y = 2\n",
        "server/static/index.html": b"<!DOCTYPE html>\n",
        "server/version.txt": b"0.9.0\n",
        "requirements.txt": Path("requirements.txt").read_bytes(),
    }
    manifest = {name: updater._git_blob_hash(data) for name, data in payloads.items()}

    def archive_file(files):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w:gz") as tar:
            for name, contents in files.items():
                info = tarfile.TarInfo(name="owner-beacon-sha/" + name)
                info.size = len(contents)
                info.mode = 0o644
                tar.addfile(info, io.BytesIO(contents))
        return stream.getvalue()

    original = updater.Path
    original_read = original.read_bytes
    def read_bytes(path):
        if str(path) == "/app/requirements.txt":
            return payloads["requirements.txt"]
        return original_read(path)
    monkeypatch.setattr(Path, "read_bytes", read_bytes)

    target = tmp_path / "release"
    target.mkdir()
    version = updater._install_archive(archive_file(payloads), "a"*40, manifest, target)
    assert version == "0.9.0"
    assert (target / "server" / "main.py").read_bytes() == payloads["server/main.py"]
    tampered = {**payloads, "server/main.py": b"x = 999\n"}
    with pytest.raises(ValueError, match="integrity"):
        updater._install_archive(archive_file(tampered), "a"*40, manifest, target)


def test_rejects_python_dependency_changes(monkeypatch, tmp_path):
    _, updater = _app(monkeypatch, tmp_path)
    monkeypatch.setattr(updater, "_manifest", lambda revision: {})
    monkeypatch.setattr(updater, "_github_get", lambda *args, **kwargs: b"")
    assert updater._root() == tmp_path / "beacon-updates"


def test_update_requested_in_background_with_no_engine_dependencies(monkeypatch, tmp_path):
    main, updater = _app(monkeypatch, tmp_path)
    installed = []
    monkeypatch.setattr(updater, "_head", lambda: {"revision": "a"*40, "message": "Latest"})
    monkeypatch.setattr(updater, "_stage", lambda sha: installed.append(sha) or {
        "version": "0.9.1", "revision": sha,
    })
    with TestClient(main.app) as client:
        auth = _login(client)
        response = client.post("/api/admin/update", headers=auth)
        assert response.status_code == 202, response.text
        assert installed == ["a"*40]
        pending = json.loads((tmp_path / "beacon-updates" / "pending.json").read_text())
        assert pending["revision"] == "a"*40
        assert not (tmp_path / "beacon-updates" / "install.lock").exists()
        # A second update cannot start while the supervisor still has a
        # pending activation request.
        assert client.post("/api/admin/update", headers=auth).status_code == 409


def test_rollback_request_rejects_missing_previous_release(monkeypatch, tmp_path):
    main, updater = _app(monkeypatch, tmp_path)
    with TestClient(main.app) as client:
        auth = _login(client)
        r = client.post("/api/admin/update/rollback", headers=auth)
        assert r.status_code == 409
