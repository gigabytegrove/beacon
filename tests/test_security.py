import importlib
import os
import tempfile

from fastapi.testclient import TestClient


def test_password_rotation_and_other_device_revocation():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["BEACON_DB"] = tmp + "/beacon.sqlite3"
        os.environ["BEACON_ADMIN_USERNAME"] = "admin"
        os.environ["BEACON_ADMIN_PASSWORD"] = "original secure admin password"
        import server.main as module
        app_module = importlib.reload(module)
        with TestClient(app_module.app) as c:
            def login(password, device):
                r = c.post("/api/login", json={
                    "username": "admin", "password": password, "device_name": device
                })
                return r
            desktop = login("original secure admin password", "desktop")
            mobile = login("original secure admin password", "mobile")
            assert desktop.status_code == mobile.status_code == 200
            a = {"Authorization": "Bearer " + desktop.json()["token"]}
            b = {"Authorization": "Bearer " + mobile.json()["token"]}
            assert c.post("/api/me/password", headers=a, json={
                "current_password": "incorrect",
                "new_password": "replacement secure admin password"
            }).status_code == 403
            assert c.get("/api/me", headers=b).status_code == 200
            assert c.post("/api/me/password", headers=a, json={
                "current_password": "original secure admin password",
                "new_password": "replacement secure admin password"
            }).json()["other_sessions_revoked"] == 1
            assert c.get("/api/me", headers=b).status_code == 401
            assert c.get("/api/me", headers=a).status_code == 200
            assert login("original secure admin password", "old credentials").status_code == 401
            third = login("replacement secure admin password", "new device")
            assert third.status_code == 200
            assert c.post("/api/sessions/revoke-others", headers=a).json()["revoked"] == 1
            t = {"Authorization": "Bearer " + third.json()["token"]}
            assert c.get("/api/me", headers=t).status_code == 401
            assert c.get("/api/me", headers=a).status_code == 200
            assert c.post("/api/sessions/revoke-others", headers=a).json()["revoked"] == 0


def test_post_aliases_for_mobile_transport():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["BEACON_DB"] = tmp + "/beacon.sqlite3"
        os.environ["BEACON_ADMIN_USERNAME"] = "admin"
        os.environ["BEACON_ADMIN_PASSWORD"] = "original secure admin password"
        import server.main as module
        main = importlib.reload(module)
        with TestClient(main.app) as c:
            token = c.post("/api/login", json={
                "username":"admin","password":"original secure admin password","device_name":"desktop"
            }).json()["token"]
            auth = {"Authorization": "Bearer " + token}
            user = c.post("/api/admin/users",headers=auth,json={
                "username":"alice","password":"secret password for alice","display_name":"Alice"
            }).json()["id"]
            group = c.post("/api/groups",headers=auth,json={"name":"Family"}).json()["id"]
            assert c.post(f"/api/groups/{group}/rename",headers=auth,
                          json={"name":"Friends"}).status_code == 200
            assert c.post(f"/api/buddies/{user}",headers=auth).status_code == 201
            assert c.post(f"/api/buddies/{user}/edit",headers=auth,json={
                "nickname":"Allie","group_id":group,"muted":True
            }).status_code == 200
            result = c.get("/api/buddies",headers=auth).json()[0]
            assert result["nickname"] == "Allie"
            assert result["group_name"] == "Friends"
            assert result["muted"] == 1
            assert main.app.version == "0.5.0"
