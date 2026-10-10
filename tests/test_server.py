import importlib
import os
import tempfile

from fastapi.testclient import TestClient


def test_beacon_account_sessions_and_dm():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["BEACON_DB"] = os.path.join(tmp, "beacon.db")
        os.environ["BEACON_ADMIN_PASSWORD"] = "correct horse battery staple"
        os.environ["BEACON_ADMIN_USERNAME"] = "admin"
        import server.main as server
        server = importlib.reload(server)
        with TestClient(server.app) as client:
            assert client.get("/health").json()["status"] == "ok"
            def login(name, pw, device):
                result = client.post("/api/login", json={"username": name, "password": pw, "device_name": device})
                assert result.status_code == 200, result.text
                return result.json()["token"]
            admin = login("admin", "correct horse battery staple", "Desktop")
            a = {"Authorization": "Bearer " + admin}
            denied = client.post("/api/admin/users", headers=a, json={"username":"alice","password":"short","display_name":"Alice"})
            assert denied.status_code == 422
            created = client.post("/api/admin/users", headers=a, json={"username":"alice","password":"alice secret password","display_name":"Alice"})
            assert created.status_code == 201, created.text
            alice_id = created.json()["id"]
            device1 = login("alice", "alice secret password", "Laptop")
            device2 = login("alice", "alice secret password", "Phone")
            assert device1 != device2
            h1 = {"Authorization": "Bearer " + device1}
            h2 = {"Authorization": "Bearer " + device2}
            assert len(client.get("/api/sessions", headers=h1).json()) == 2
            assert client.post("/api/admin/users", headers=h1, json={"username":"eve","password":"super secret password","display_name":"Eve"}).status_code == 403
            with client.websocket_connect("/api/ws") as ws:
                ws.send_json({"type": "auth", "token": device1})
                assert ws.receive_json()["type"] == "ready"
                sent = client.post("/api/messages", headers=a, json={"recipient_id": alice_id, "body": "Hello!"})
                assert sent.status_code == 201, sent.text
                evt = ws.receive_json()
                assert evt["type"] == "message"
                assert evt["message"]["body"] == "Hello!"
            assert len(client.get("/api/messages/1", headers=h2).json()) == 1
            assert client.get("/api/messages/1").status_code == 401
            assert client.post("/api/messages", headers=h1, json={"recipient_id": alice_id, "body": "bad"}).status_code == 422
            sessions = client.get("/api/sessions", headers=h1).json()
            other = next(s for s in sessions if not s["current"])
            assert client.delete(f"/api/sessions/{other['id']}", headers=h1).status_code == 200
            assert client.get("/api/me", headers=h2).status_code == 401
            assert client.get("/api/me", headers=h1).status_code == 200
            assert client.post("/api/logout", headers=h1).status_code == 200
            assert client.get("/api/me", headers=h1).status_code == 401
