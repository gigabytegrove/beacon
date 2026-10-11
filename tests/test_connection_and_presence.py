"""Stress-safe DB connection scope and aggregated AIM roster presence."""
import importlib
import os
import sqlite3
import tempfile

import pytest
from fastapi.testclient import TestClient


def setup_test_server(tmp):
    os.environ["BEACON_DB"] = tmp + "/beacon.sqlite3"
    os.environ["BEACON_ADMIN_USERNAME"] = "admin"
    os.environ["BEACON_ADMIN_PASSWORD"] = "secure and unique admin passphrase"
    import server.main as module
    module = importlib.reload(module)
    return module


def authorization(client, username, password):
    response = client.post("/api/login", json={
        "username": username, "password": password, "device_name": "test-client"
    })
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["token"]}


def test_connection_closes_and_rolls_back_on_exception():
    with tempfile.TemporaryDirectory() as tmp:
        main = setup_test_server(tmp)
        with TestClient(main.app):
            with main.connection() as db:
                assert db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
                exposed = db
            with pytest.raises(sqlite3.ProgrammingError):
                exposed.execute("SELECT 1")
            with pytest.raises(RuntimeError):
                with main.connection() as db:
                    db.execute("UPDATE users SET display_name='UNCOMMITTED' WHERE username='admin'")
                    raise RuntimeError("abort transaction")
            with main.connection() as db:
                display = db.execute(
                    "SELECT display_name FROM users WHERE username='admin'"
                ).fetchone()[0]
                assert display != "UNCOMMITTED"


def test_roster_multidevice_presence_aggregation_and_ownership():
    with tempfile.TemporaryDirectory() as tmp:
        main = setup_test_server(tmp)
        with TestClient(main.app) as client:
            admin = authorization(client, "admin", "secure and unique admin passphrase")
            ids = []
            headers = []
            for number in range(4):
                username = "testuser" + str(number)
                response = client.post("/api/admin/users", headers=admin, json={
                    "username": username, "display_name": "Test User " + str(number),
                    "password": "long test password " + str(number),
                })
                assert response.status_code == 201, response.text
                ids.append(response.json()["id"])
                headers.append(authorization(client, username, "long test password " + str(number)))
                assert client.post("/api/buddies/" + str(ids[-1]), headers=admin).status_code == 201
            for status, hdr in zip(("away", "busy", "available", "away"), headers):
                response = client.post("/api/presence", headers=hdr, json={"status": status})
                assert response.status_code == 200, response.text
            roster = client.get("/api/buddies", headers=admin)
            assert roster.status_code == 200, roster.text
            by_id = {row["id"]: row for row in roster.json()}
            assert [by_id[user]["presence"] for user in ids] == ["away", "busy", "available", "away"]
            directory = client.get("/api/directory", headers=admin)
            assert directory.status_code == 200, directory.text
            people = {row["id"]: row for row in directory.json()}
            assert all(people[user]["presence"] == by_id[user]["presence"] for user in ids)
            assert client.get("/api/buddies", headers=headers[0]).json() == []
            # Second device for the same user changes the aggregate status.
            second = authorization(client, "testuser0", "long test password 0")
            assert client.post("/api/presence", headers=second, json={"status": "available"}).status_code == 200
            assert client.get("/api/buddies", headers=admin).json()[0]["presence"] == "available"
            assert client.get("/api/buddies").status_code == 401
            # The roster renderer must not issue one SELECT per buddy.
            from server import aim
            with main.connection() as db:
                rows = db.execute(
                    "SELECT id,username,display_name,status_text,avatar "
                    "FROM users WHERE id<>1"
                ).fetchall()
                statements = []
                db.set_trace_callback(statements.append)
                enriched = aim.attach_presence(db, rows)
                assert len(enriched) == 4
                presence_reads = [
                    statement for statement in statements
                    if "FROM sessions WHERE user_id IN" in statement
                ]
                assert len(presence_reads) == 1
