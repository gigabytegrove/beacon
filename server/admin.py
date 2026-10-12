"""Administrator-only operational controls for the self-hosted Beacon server.

The browser management center uses these APIs. All database access is scoped to
the authenticated administrator and never returns password hashes or tokens.
"""
from __future__ import annotations

import os
import time
import sqlite3
from fastapi import HTTPException, Request
from pydantic import BaseModel, Field


class AdminResetPassword(BaseModel):
    password: str = Field(min_length=12, max_length=256)


class ServerSettings(BaseModel):
    server_name: str = Field(min_length=2, max_length=64)
    tagline: str = Field(min_length=1, max_length=120)


def register(app, *, current, connection, lock, hash_password, disconnect_session):
    started = time.time()

    def administrator(request: Request):
        user = current(request)
        if not user["is_admin"]:
            raise HTTPException(403, "Administrator access required")
        return user

    @app.get("/api/admin/overview")
    def admin_overview(request: Request):
        administrator(request)
        now = int(time.time())
        with connection() as db:
            counters = {
                "users": db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
                "active_sessions": db.execute("SELECT COUNT(*) FROM sessions WHERE expires_at>?", (now,)).fetchone()[0],
                "messages": db.execute("SELECT COUNT(*) FROM messages").fetchone()[0],
                "buddy_links": db.execute("SELECT COUNT(*) FROM buddies").fetchone()[0],
                "online_users": db.execute(
                    "SELECT COUNT(DISTINCT user_id) FROM sessions "
                    "WHERE expires_at>? AND last_seen>? AND presence<>'offline'",
                    (now, now-90)
                ).fetchone()[0]
            }
            settings = {row["key"]: row["value"] for row in db.execute(
                "SELECT key,value FROM server_settings")}
        db_bytes = 0
        try:
            db_bytes = os.stat(os.getenv("BEACON_DB", "/data/beacon.db")).st_size
        except OSError:
            pass
        return {
            "status": "running",
            "uptime_seconds": int(time.time() - started),
            "database_bytes": db_bytes,
            **counters,
            "server_name": settings.get("server_name", "Beacon"),
            "tagline": settings.get("tagline", "Your people. Your network.")
        }

    @app.get("/api/admin/users")
    def admin_list_users(request: Request):
        administrator(request)
        with connection() as db:
            rows = db.execute(
                "SELECT u.id,u.username,u.display_name,u.is_admin,u.created_at,"
                "(SELECT COUNT(*) FROM sessions s WHERE s.user_id=u.id "
                "AND s.expires_at>?) AS sessions "
                "FROM users u ORDER BY lower(u.username)",
                (int(time.time()),)
            ).fetchall()
        return [dict(r) for r in rows]

    @app.get("/api/admin/sessions")
    def admin_list_sessions(request: Request):
        administrator(request)
        now = int(time.time())
        with connection() as db:
            rows = db.execute(
                "SELECT s.id,s.user_id,u.username,s.device_name,"
                "s.created_at,s.last_seen,s.expires_at,s.presence "
                "FROM sessions s JOIN users u ON u.id=s.user_id "
                "WHERE s.expires_at>? ORDER BY s.last_seen DESC,s.id DESC LIMIT 500",
                (now,)
            ).fetchall()
        return [dict(r) for r in rows]

    @app.delete("/api/admin/sessions/{session_id}")
    async def admin_revoke_session(session_id: int, request: Request):
        actor = administrator(request)
        if session_id == actor["session_id"]:
            raise HTTPException(409, "Sign out from your own device using Sign out")
        with lock, connection() as db:
            result = db.execute("DELETE FROM sessions WHERE id=?", (session_id,))
            if not result.rowcount:
                raise HTTPException(404, "Session not found")
        await disconnect_session(session_id)
        return {"ok": True}

    @app.post("/api/admin/users/{user_id}/reset-password")
    async def admin_reset_password(user_id: int, data: AdminResetPassword, request: Request):
        actor = administrator(request)
        if actor["id"] == user_id:
            raise HTTPException(409, "Change your own password from your account preferences")
        with lock, connection() as db:
            row = db.execute("SELECT id FROM users WHERE id=?", (user_id,)).fetchone()
            if row is None:
                raise HTTPException(404, "User not found")
            hashed = hash_password(data.password)
            db.execute("UPDATE users SET password_hash=? WHERE id=?", (hashed, user_id))
            ids = [r["id"] for r in db.execute("SELECT id FROM sessions WHERE user_id=?", (user_id,))]
            db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
        for session_id in ids:
            await disconnect_session(session_id)
        return {"ok": True, "sessions_revoked": len(ids)}

    @app.get("/api/admin/settings")
    def admin_get_settings(request: Request):
        administrator(request)
        with connection() as db:
            settings = {r["key"]: r["value"] for r in db.execute(
                "SELECT key,value FROM server_settings")}
        return {"server_name": settings.get("server_name", "Beacon"),
                "tagline": settings.get("tagline", "Your people. Your network.")}

    @app.put("/api/admin/settings")
    def admin_save_settings(data: ServerSettings, request: Request):
        administrator(request)
        if not data.server_name.strip() or not data.tagline.strip():
            raise HTTPException(422, "Server name and tagline cannot be empty")
        with lock, connection() as db:
            for key,value in [("server_name",data.server_name.strip()),
                              ("tagline",data.tagline.strip())]:
                db.execute(
                    "INSERT INTO server_settings(key,value) VALUES (?,?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key,value))
        return {"server_name": data.server_name.strip(), "tagline": data.tagline.strip()}
