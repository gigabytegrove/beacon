"""Beacon server management API should not expose controls to ordinary members."""
import importlib
import os
from fastapi.testclient import TestClient


def test_admin_center_is_protected_and_operational(tmp_path, monkeypatch):
    monkeypatch.setenv("BEACON_DB",str(tmp_path/"beacon.db"))
    monkeypatch.setenv("BEACON_ADMIN_USERNAME","admin")
    monkeypatch.setenv("BEACON_ADMIN_PASSWORD","correct horse battery staple")
    import server.main as server
    server=importlib.reload(server)
    with TestClient(server.app) as client:
        admin=client.post("/api/login",json={"username":"admin","password":"correct horse battery staple","device_name":"Browser"}).json()["token"]
        auth={"Authorization":"Bearer "+admin}
        overview=client.get("/api/admin/overview",headers=auth)
        assert overview.status_code==200,overview.text
        assert overview.json()["users"]==1
        assert overview.json()["active_sessions"]==1
        assert client.get("/api/admin/users",headers=auth).status_code==200
        assert client.get("/api/admin/sessions",headers=auth).status_code==200
        assert client.put("/api/admin/settings",headers=auth,json={"server_name":"Family Beacon","tagline":"Stay in touch"}).status_code==200
        assert client.get("/api/admin/settings",headers=auth).json()["server_name"]=="Family Beacon"
        assert client.get("/api/admin/overview").status_code==401
        assert client.post("/api/admin/users",headers=auth,json={"username":"member","password":"member secure pass","display_name":"Member"}).status_code==201
        member_token=client.post("/api/login",json={"username":"member","password":"member secure pass","device_name":"Phone"}).json()["token"]
        member={"Authorization":"Bearer "+member_token}
        for path in ("/api/admin/overview","/api/admin/users","/api/admin/sessions","/api/admin/settings"):
            assert client.get(path,headers=member).status_code==403
        assert client.post("/api/admin/users/2/reset-password",headers=auth,json={"password":"replaced member password"}).status_code==200
        assert client.get("/api/me",headers=member).status_code==401
        assert client.post("/api/login",json={"username":"member","password":"replaced member password","device_name":"Phone"}).status_code==200
