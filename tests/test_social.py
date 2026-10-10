"""End-to-end buddy organization, account isolation and notifications API tests."""
import importlib
import os
import tempfile

from fastapi.testclient import TestClient


def test_groups_nicknames_mutes_and_ownership():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["BEACON_DB"] = tmp + "/chat.sqlite3"
        os.environ["BEACON_ADMIN_PASSWORD"] = "long unique admin password"
        os.environ["BEACON_ADMIN_USERNAME"] = "admin"
        import server.main as module
        main = importlib.reload(module)
        with TestClient(main.app) as client:
            def login(username, password):
                response = client.post("/api/login", json={
                    "username": username, "password": password, "device_name": "test-device"
                })
                assert response.status_code == 200, response.text
                return {"Authorization": "Bearer " + response.json()["token"]}
            admin = login("admin", "long unique admin password")
            people = [
                ("alice", "Alice", "password for alice 123"),
                ("bob", "Bob", "password for bob 123"),
            ]
            ids = {}
            for username, display, password in people:
                result = client.post("/api/admin/users", headers=admin, json={
                    "username":username,"display_name":display,"password":password
                })
                assert result.status_code == 201, result.text
                ids[username] = result.json()["id"]
            assert client.post("/api/admin/users", headers=admin, json={
                "username":"ALICE","display_name":"Duplicate","password":"invalid duplicate password"
            }).status_code == 409
            alice = login("alice", "password for alice 123")
            bob = login("bob", "password for bob 123")
            assert client.get("/api/groups").status_code == 401
            assert client.post("/api/groups", headers=admin, json={"name":"Buddies"}).status_code == 422
            group = client.post("/api/groups", headers=admin, json={"name":"Family"})
            assert group.status_code == 201, group.text
            gid = group.json()["id"]
            assert client.post("/api/groups", headers=admin, json={"name":"family"}).status_code == 409
            assert client.get("/api/groups", headers=alice).json() == []
            assert client.patch("/api/groups/" + str(gid), headers=alice,
                                json={"name":"Not mine"}).status_code == 404
            assert client.patch("/api/buddies/" + str(ids["alice"]), headers=alice,
                                json={"group_id":gid}).status_code == 422
            assert client.post("/api/buddies/" + str(ids["alice"]), headers=admin).status_code == 201
            settings = client.patch("/api/buddies/" + str(ids["alice"]), headers=admin,
                json={"nickname":"Allie","group_id":gid,"muted":True})
            assert settings.status_code == 200, settings.text
            roster = client.get("/api/buddies", headers=admin).json()
            assert len(roster) == 1
            assert roster[0]["nickname"] == "Allie"
            assert roster[0]["group_name"] == "Family"
            assert roster[0]["group_id"] == gid
            assert roster[0]["muted"] == 1
            assert client.patch("/api/buddies/" + str(ids["bob"]), headers=admin,
                                json={"nickname":"B"}).status_code == 404
            assert client.patch("/api/buddies/" + str(ids["alice"]), headers=admin,
                                json={"muted":None}).status_code == 422
            assert client.patch("/api/groups/" + str(gid), headers=admin,
                                json={"name":"Relatives"}).status_code == 200
            assert client.get("/api/buddies", headers=admin).json()[0]["group_name"] == "Relatives"
            assert client.delete("/api/groups/" + str(gid), headers=bob).status_code == 404
            assert client.delete("/api/groups/" + str(gid), headers=admin).status_code == 200
            updated = client.get("/api/buddies", headers=admin).json()[0]
            assert updated["group_id"] is None
            assert updated["group_name"] == "Buddies"
            assert updated["nickname"] == "Allie"
            assert client.patch("/api/buddies/" + str(ids["alice"]), headers=admin,
                                json={"nickname":"","muted":False}).status_code == 200
            updated = client.get("/api/buddies", headers=admin).json()[0]
            assert updated["nickname"] == ""
            assert updated["muted"] == 0
            assert client.delete("/api/buddies/" + str(ids["alice"]), headers=admin).status_code == 200
            assert client.get("/api/buddies", headers=admin).json() == []


def test_roster_document_and_chat_route():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["BEACON_DB"] = tmp + "/beacon.db"
        os.environ["BEACON_ADMIN_PASSWORD"] = "long unique admin password"
        os.environ["BEACON_ADMIN_USERNAME"] = "admin"
        import server.main as module
        main = importlib.reload(module)
        with TestClient(main.app) as client:
            root = client.get("/")
            assert root.status_code == 200
            assert b"buddyDialog" in root.content
            assert b"groupsDialog" in root.content
            assert b"soundEnabled" in root.content
            assert client.get("/chat/1").status_code == 200
