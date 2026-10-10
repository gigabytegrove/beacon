import importlib
import os
import tempfile
from fastapi.testclient import TestClient


def test_buddy_list_presence_typing_avatar_and_read_sync():
    with tempfile.TemporaryDirectory() as directory:
        os.environ["BEACON_DB"] = directory + "/beacon.sqlite"
        os.environ["BEACON_ADMIN_PASSWORD"] = "secure temporary admin password"
        os.environ["BEACON_ADMIN_USERNAME"] = "admin"
        import server.main
        main = importlib.reload(server.main)
        with TestClient(main.app) as client:
            def login(user, password, device):
                response = client.post("/api/login", json={"username": user, "password": password, "device_name": device})
                assert response.status_code == 200, response.text
                return {"Authorization": "Bearer " + response.json()["token"]}, response.json()["token"]
            admin, at = login("admin", "secure temporary admin password", "Admin desktop")
            create = client.post("/api/admin/users", headers=admin,
                                 json={"username":"alice","display_name":"Alice","password":"secret password for alice"})
            assert create.status_code == 201, create.text
            uid = create.json()["id"]
            a1, tok1 = login("alice", "secret password for alice", "Phone")
            a2, tok2 = login("alice", "secret password for alice", "PC")
            assert client.get("/api/buddies", headers=admin).json() == []
            assert client.post("/api/buddies/" + str(uid), headers=admin).status_code == 201
            assert len(client.get("/api/buddies", headers=admin).json()) == 1
            assert client.post("/api/buddies/1", headers=a1).status_code == 201
            with client.websocket_connect("/api/ws") as ws:
                ws.send_json({"type":"auth","token":tok1})
                assert ws.receive_json()["type"] == "ready"
                assert client.get("/api/buddies", headers=admin).json()[0]["presence"] == "available"
                assert client.post("/api/typing/1", headers=a1, json={"active":True}).status_code == 200
                assert client.get("/api/typing/" + str(uid), headers=admin).json()["active"]
                msg = client.post("/api/messages",headers=admin,json={"recipient_id":uid,"body":"Hello from Beacon"})
                assert msg.status_code == 201
                assert ws.receive_json()["type"] == "message"
                buddies = client.get("/api/buddies",headers=a2).json()
                assert buddies[0]["unread_count"] == 1
                mid = msg.json()["id"]
                read = client.post("/api/conversations/1/read",headers=a1,json={"through_id":mid})
                assert read.status_code == 200
                assert client.get("/api/buddies",headers=a2).json()[0]["unread_count"] == 0
                assert client.get("/api/events",headers=a1).json()["next_cursor"] == mid
                assert client.post("/api/me/avatar",headers=a1,json={"image_base64":"not-base64","mime_type":"image/png"}).status_code == 422
                assert client.put("/api/me/profile",headers=a1,json={"display_name":"Alice B","status_text":"At my desk"}).status_code == 200
                assert client.get("/api/buddies",headers=admin).json()[0]["display_name"] == "Alice B"
                sessions = client.get("/api/sessions",headers=a2).json()
                other = next(s for s in sessions if not s["current"])
                assert client.delete("/api/sessions/" + str(other["id"]),headers=a2).status_code == 200
                assert client.get("/api/me",headers=a1).status_code == 401
                assert client.get("/api/me",headers=a2).status_code == 200
            assert client.delete("/api/buddies/" + str(uid),headers=admin).status_code == 200
            assert client.get("/api/buddies",headers=admin).json() == []
