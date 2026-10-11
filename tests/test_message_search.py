import importlib
import os
import tempfile
from fastapi.testclient import TestClient


def test_search_is_account_scoped_and_escapes_like_patterns():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["BEACON_DB"] = tmp + "/beacon.sqlite3"
        os.environ["BEACON_ADMIN_USERNAME"] = "admin"
        os.environ["BEACON_ADMIN_PASSWORD"] = "secure admin password 123"
        import server.main as server
        server = importlib.reload(server)
        with TestClient(server.app) as client:
            def login(user, password):
                r = client.post("/api/login", json={
                    "username": user, "password": password, "device_name": "test"
                })
                assert r.status_code == 200, r.text
                return {"Authorization": "Bearer " + r.json()["token"]}
            admin = login("admin", "secure admin password 123")
            ids = {}
            for name in ("alice", "bob", "eve"):
                r = client.post("/api/admin/users", headers=admin, json={
                    "username":name, "display_name":name,
                    "password": "a long password for " + name
                })
                assert r.status_code == 201
                ids[name] = r.json()["id"]
            alice = login("alice", "a long password for alice")
            bob = login("bob", "a long password for bob")
            eve = login("eve", "a long password for eve")
            messages = [
                (alice, ids["bob"], "LAN testing 100%"),
                (bob, ids["alice"], "LAN testing underscore_name"),
                (eve, ids["bob"], "LAN testing private to Bob"),
                (admin, ids["eve"], "LAN testing private to Eve"),
            ]
            for headers, recipient, body in messages:
                r = client.post("/api/messages", headers=headers, json={
                    "recipient_id": recipient, "body": body
                })
                assert r.status_code == 201, r.text
            assert client.get("/api/messages/search?q=LAN").status_code == 401
            result = client.get("/api/messages/search?q=LAN", headers=alice)
            assert result.status_code == 200, result.text
            assert len(result.json()) == 2
            assert all("private" not in row["body"] for row in result.json())
            result = client.get("/api/messages/search?q=100%25", headers=alice)
            assert [row["body"] for row in result.json()] == ["LAN testing 100%"]
            result = client.get("/api/messages/search?q=underscore_name", headers=alice)
            assert len(result.json()) == 1
            result = client.get("/api/messages/search?q=LAN&peer_id=" + str(ids["bob"]), headers=alice)
            assert len(result.json()) == 2
            result = client.get("/api/messages/search?q=LAN&peer_id=" + str(ids["eve"]), headers=alice)
            assert result.json() == []
            assert client.get("/api/messages/search?q=a", headers=alice).status_code == 422
            assert client.get("/api/messages/search?q=LAN&limit=999", headers=alice).status_code == 422
            assert client.get("/api/messages/search?q=LAN&peer_id=99999", headers=alice).status_code == 404
