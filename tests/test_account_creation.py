"""Account management regression tests for Beacon's server control center."""
import importlib

from fastapi.testclient import TestClient


def app_with_admin(monkeypatch, tmp_path):
    monkeypatch.setenv("BEACON_DB", str(tmp_path / "beacon.db"))
    monkeypatch.setenv("BEACON_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("BEACON_ADMIN_PASSWORD", "correct horse battery staple")
    import server.main as main
    main = importlib.reload(main)
    return main.app


def log_in(client, username, password):
    res = client.post("/api/login", json={
        "username": username,
        "password": password,
        "device_name": "Browser",
    })
    assert res.status_code == 200, res.text
    return {"Authorization": "Bearer " + res.json()["token"]}


def test_create_account_validation_and_visible_management(monkeypatch, tmp_path):
    app = app_with_admin(monkeypatch, tmp_path)
    with TestClient(app) as client:
        auth = log_in(client, "admin", "correct horse battery staple")
        url = "/api/admin/users"
        assert client.post(url, json={
            "username": "new_member", "display_name": "New Member",
            "password": "long secure password",
        }).status_code == 401

        invalid = [
            ({"username": "ab", "display_name": "Short", "password": "valid password"}, "username"),
            ({"username": "<script>", "display_name": "Unsafe", "password": "valid password"}, "username"),
            ({"username": "member_1", "display_name": "Member", "password": "short"}, "password"),
            ({"username": "member_1", "display_name": "A" * 81, "password": "valid password"}, "display_name"),
        ]
        for body, field in invalid:
            response = client.post(url, headers=auth, json=body)
            assert response.status_code == 422, (body, response.text)
            detail = response.json()["detail"]
            assert isinstance(detail, list)
            assert any(item["loc"][-1] == field for item in detail)

        blank_name = client.post(url, headers=auth, json={
            "username": "member_1", "display_name": "   ",
            "password": "valid password",
        })
        assert blank_name.status_code == 422
        assert blank_name.json()["detail"] == "Display name must not be empty"

        user = {
            "username": "member_1", "display_name": "  Member One  ",
            "password": "valid password for member",
        }
        created = client.post(url, headers=auth, json=user)
        assert created.status_code == 201, created.text
        assert created.json()["username"] == "member_1"
        assert created.json()["display_name"] == "Member One"
        assert created.json()["role"] == "member"
        assert isinstance(created.json()["id"], int)

        duplicate = client.post(url, headers=auth, json={
            **user, "username": "MEMBER_1",
        })
        assert duplicate.status_code == 409
        assert "already exists" in duplicate.json()["detail"].lower()

        users = client.get(url, headers=auth)
        assert users.status_code == 200, users.text
        listed = next(row for row in users.json() if row["username"] == "member_1")
        assert listed["display_name"] == "Member One"
        assert listed["is_admin"] == 0
        assert listed["sessions"] == 0
        assert listed["created_at"] > 0
        assert "password" not in listed
        assert "password_hash" not in listed

        member = log_in(client, "member_1", "valid password for member")
        assert client.get(url, headers=member).status_code == 403
        assert client.post(url, headers=member, json={
            "username": "blocked", "display_name": "Blocked",
            "password": "not allowed password",
        }).status_code == 403


def test_management_page_exposes_real_validated_form_and_clear_errors(monkeypatch, tmp_path):
    app = app_with_admin(monkeypatch, tmp_path)
    with TestClient(app) as client:
        page = client.get("/")
        assert page.status_code == 200
        html = page.text
        assert 'id="createUserForm"' in html
        assert 'id="newUsername"' in html
        assert 'pattern="[A-Za-z0-9_.-]{3,32}"' in html
        assert 'id="newPasswordConfirm"' in html
        assert 'id="createUserError"' in html
        assert 'id="adminUserSearch"' in html
        assert 'id="adminUsersCount"' in html
        assert 'id="adminRefreshUsers"' in html
        assert 'id="adminResetError"' in html
        assert 'apiErrorMessage(' in html
        assert 'Array.isArray(detail)' in html
        assert '$("createUserForm").onsubmit=' in html
        assert '$("adminCreateUser").onclick=openCreateUser' in html
