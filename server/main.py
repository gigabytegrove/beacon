import asyncio
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

DB = os.getenv("BEACON_DB", "/data/beacon.db")
LOCK = threading.RLock()
SESSION_AGE = 30 * 86400
LOGIN_ATTEMPTS = defaultdict(deque)
CHANNELS: dict[int, set[WebSocket]] = defaultdict(set)
WS_SESSIONS: dict[WebSocket, int] = {}
USERNAME = re.compile(r"^[a-zA-Z0-9_.-]{3,32}$")


def connection():
    db = sqlite3.connect(DB, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=10000")
    return db


def password_hash(password: str, salt: bytes | None = None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return salt.hex() + ":" + digest.hex()


def verify_password(password, stored):
    try:
        salt, digest = stored.split(":")
        actual = password_hash(password, bytes.fromhex(salt)).split(":")[1]
        return hmac.compare_digest(actual, digest)
    except (ValueError, TypeError):
        return False


def init_db():
    Path(DB).parent.mkdir(parents=True, exist_ok=True)
    with LOCK, connection() as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL, password_hash TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions(
            id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token_hash TEXT UNIQUE NOT NULL, device_name TEXT NOT NULL,
            created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages(
            id INTEGER PRIMARY KEY, sender_id INTEGER NOT NULL REFERENCES users(id),
            recipient_id INTEGER NOT NULL REFERENCES users(id),
            body TEXT NOT NULL, created_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_messages_inbox ON messages(recipient_id,id);
        CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender_id,id);
        CREATE TABLE IF NOT EXISTS buddies(
            owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            buddy_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            PRIMARY KEY(owner_id, buddy_id)
        );
        CREATE TABLE IF NOT EXISTS read_cursors(
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            peer_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            last_read_id INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(user_id, peer_id)
        );
        """)
        for table, column, definition in (
            ("users", "avatar", "TEXT NOT NULL DEFAULT ''"),
            ("users", "status_text", "TEXT NOT NULL DEFAULT ''"),
            ("sessions", "last_seen", "INTEGER NOT NULL DEFAULT 0"),
            ("sessions", "presence", "TEXT NOT NULL DEFAULT 'available'"),
        ):
            if column not in {r["name"] for r in db.execute("PRAGMA table_info(" + table + ")")}:
                db.execute("ALTER TABLE " + table + " ADD COLUMN " + column + " " + definition)
        if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            username = os.getenv("BEACON_ADMIN_USERNAME", "admin")
            password = os.getenv("BEACON_ADMIN_PASSWORD", "")
            if not USERNAME.fullmatch(username) or len(password) < 12 or password == "REPLACE_WITH_A_LONG_RANDOM_PASSWORD":
                raise RuntimeError("Set a valid BEACON_ADMIN_USERNAME and a unique BEACON_ADMIN_PASSWORD (minimum 12 chars)")
            db.execute(
                "INSERT INTO users(username,display_name,password_hash,is_admin,created_at) VALUES (?,?,?,?,?)",
                (username, username, password_hash(password), 1, int(time.time())),
            )
        db.execute("DELETE FROM sessions WHERE expires_at <= ?", (int(time.time()),))


@asynccontextmanager
async def lifespan(app):
    init_db()
    from . import aim
    sweeper = asyncio.create_task(aim.presence_sweeper())
    try:
        yield
    finally:
        sweeper.cancel()
        try:
            await sweeper
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Beacon", version="0.3.0", lifespan=lifespan)


def auth_token(token):
    if not token:
        raise HTTPException(401, "Authentication required")
    digest = hashlib.sha256(token.encode()).hexdigest()
    with connection() as db:
        row = db.execute("""
          SELECT u.id,u.username,u.display_name,u.is_admin,s.id AS session_id
          FROM sessions s JOIN users u ON u.id=s.user_id
          WHERE s.token_hash=? AND s.expires_at>?
        """, (digest, int(time.time()))).fetchone()
    if row is None:
        raise HTTPException(401, "Invalid or expired session")
    return dict(row)


def current(request: Request):
    value = request.headers.get("authorization", "")
    return auth_token(value[7:] if value.startswith("Bearer ") else None)


class Credentials(BaseModel):
    username: str
    password: str
    device_name: str = Field(min_length=1, max_length=80)


class NewUser(BaseModel):
    username: str
    password: str = Field(min_length=12, max_length=256)
    display_name: str = Field(min_length=1, max_length=80)


class NewMessage(BaseModel):
    recipient_id: int
    body: str = Field(min_length=1, max_length=4000)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def home():
    return FileResponse(Path(__file__).parent / "static" / "index.html", headers={"Cache-Control": "no-store"})


@app.post("/api/login")
def login(data: Credentials, request: Request):
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    with LOCK:
        attempts = LOGIN_ATTEMPTS[ip]
        while attempts and attempts[0] < now - 900:
            attempts.popleft()
        if len(attempts) >= 10:
            raise HTTPException(429, "Too many login attempts; try again later")
        with connection() as db:
            row = db.execute("SELECT * FROM users WHERE username=? COLLATE NOCASE", (data.username,)).fetchone()
            if row is None or not verify_password(data.password, row["password_hash"]):
                attempts.append(now)
                raise HTTPException(401, "Incorrect username or password")
            attempts.clear()
            raw_token = secrets.token_urlsafe(48)
            db.execute(
                "INSERT INTO sessions(user_id,token_hash,device_name,created_at,expires_at) VALUES (?,?,?,?,?)",
                (row["id"], hashlib.sha256(raw_token.encode()).hexdigest(), data.device_name, int(time.time()), int(time.time()) + SESSION_AGE),
            )
    return {"token": raw_token, "user": {"id": row["id"], "username": row["username"], "display_name": row["display_name"], "is_admin": bool(row["is_admin"])}}


@app.post("/api/logout")
async def logout(request: Request):
    user = current(request)
    with LOCK, connection() as db:
        db.execute("DELETE FROM sessions WHERE id=? AND user_id=?", (user["session_id"], user["id"]))
    await disconnect_session(user["session_id"])
    from .aim import clear_presence
    await clear_presence(user["id"], user["session_id"])
    return {"ok": True}


@app.get("/api/me")
def me(request: Request):
    return current(request)


@app.get("/api/users")
def users(request: Request):
    current(request)
    with connection() as db:
        rows = db.execute("SELECT id,username,display_name FROM users ORDER BY display_name").fetchall()
    return [dict(row) for row in rows]


@app.post("/api/admin/users", status_code=201)
def create_user(data: NewUser, request: Request):
    actor = current(request)
    if not actor["is_admin"]:
        raise HTTPException(403, "Administrator required")
    if not USERNAME.fullmatch(data.username):
        raise HTTPException(422, "Username must be 3-32 letters, digits, _, . or -")
    with LOCK, connection() as db:
        try:
            result = db.execute(
                "INSERT INTO users(username,display_name,password_hash,created_at) VALUES (?,?,?,?)",
                (data.username, data.display_name.strip(), password_hash(data.password), int(time.time())),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(409, "Username already exists")
    return {"id": result.lastrowid, "username": data.username}


@app.get("/api/sessions")
def sessions(request: Request):
    actor = current(request)
    with connection() as db:
        rows = db.execute("SELECT id,device_name,created_at,expires_at FROM sessions WHERE user_id=? AND expires_at>? ORDER BY id DESC", (actor["id"], int(time.time()))).fetchall()
    return [dict(row) | {"current": row["id"] == actor["session_id"]} for row in rows]


@app.delete("/api/sessions/{session_id}")
async def revoke_session(session_id: int, request: Request):
    actor = current(request)
    with LOCK, connection() as db:
        result = db.execute("DELETE FROM sessions WHERE id=? AND user_id=?", (session_id, actor["id"]))
    if not result.rowcount:
        raise HTTPException(404, "Session not found")
    await disconnect_session(session_id)
    from .aim import clear_presence
    await clear_presence(actor["id"], session_id)
    return {"ok": True}


@app.get("/api/messages/{other_id}")
def history(other_id: int, request: Request, before: int | None = None):
    actor = current(request)
    with connection() as db:
        if not db.execute("SELECT 1 FROM users WHERE id=?", (other_id,)).fetchone():
            raise HTTPException(404, "User not found")
        rows = db.execute("""
            SELECT id,sender_id,recipient_id,body,created_at FROM messages
            WHERE ((sender_id=? AND recipient_id=?) OR (sender_id=? AND recipient_id=?))
            AND (? IS NULL OR id < ?) ORDER BY id DESC LIMIT 100
        """, (actor["id"], other_id, other_id, actor["id"], before, before)).fetchall()
    return [dict(row) for row in reversed(rows)]


async def publish(user_id, message):
    dead = []
    for ws in list(CHANNELS.get(user_id, ())):
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        CHANNELS[user_id].discard(ws)


async def disconnect_session(session_id):
    for ws, sid in list(WS_SESSIONS.items()):
        if sid == session_id:
            try:
                await ws.close(code=4001)
            except Exception:
                pass


async def disconnect_user(user_id):
    # Force clients to reauthenticate when one of a user's sessions changes.
    for ws in list(CHANNELS.get(user_id, ())):
        try:
            await ws.close(code=4001)
        except Exception:
            pass
    CHANNELS.pop(user_id, None)


@app.post("/api/messages", status_code=201)
async def send(data: NewMessage, request: Request):
    actor = current(request)
    if data.recipient_id == actor["id"]:
        raise HTTPException(422, "Select a different user")
    if not data.body.strip():
        raise HTTPException(422, "Message cannot be blank")
    with LOCK, connection() as db:
        if not db.execute("SELECT 1 FROM users WHERE id=?", (data.recipient_id,)).fetchone():
            raise HTTPException(404, "Recipient not found")
        timestamp = int(time.time())
        result = db.execute("INSERT INTO messages(sender_id,recipient_id,body,created_at) VALUES (?,?,?,?)",
                            (actor["id"], data.recipient_id, data.body, timestamp))
        payload = {"id": result.lastrowid, "sender_id": actor["id"], "recipient_id": data.recipient_id, "body": data.body, "created_at": timestamp}
    event = {"type": "message", "message": payload}
    await publish(actor["id"], event)
    await publish(data.recipient_id, event)
    return payload


@app.websocket("/api/ws")
async def websocket(ws: WebSocket):
    # Authenticate in the first message; tokens never appear in URL query strings.
    origin = ws.headers.get("origin")
    host = ws.headers.get("host", "")
    if origin:
        from urllib.parse import urlparse
        if urlparse(origin).netloc != host:
            await ws.close(code=1008)
            return
    await ws.accept()
    user_id = None
    try:
        payload = await asyncio.wait_for(ws.receive_json(), timeout=10)
        if not isinstance(payload, dict) or payload.get("type") != "auth":
            await ws.close(code=1008)
            return
        try:
            actor = auth_token(payload.get("token"))
        except HTTPException:
            await ws.close(code=1008)
            return
        user_id = actor["id"]
        CHANNELS[user_id].add(ws)
        WS_SESSIONS[ws] = actor["session_id"]
        from . import aim
        await aim.set_presence(user_id, actor["session_id"], "available")
        await ws.send_json({"type": "ready", "user_id": user_id})
        while True:
            # Revalidate after connection; session revocations take effect.
            try:
                auth_token(payload["token"])
            except HTTPException:
                await ws.close(code=4001)
                return
            incoming = await ws.receive_text()
            if incoming == "ping":
                await aim.touch_presence(user_id, actor["session_id"])
                await ws.send_text("pong")
                continue
            try:
                message = json.loads(incoming)
            except json.JSONDecodeError:
                continue
            if not isinstance(message, dict):
                continue
            if message.get("type") == "typing":
                await aim.send_typing(user_id, message.get("recipient_id"), message.get("active") is True)
            elif message.get("type") == "presence" and message.get("status") in ("available","away","busy"):
                await aim.set_presence(user_id, actor["session_id"], message["status"])
    except asyncio.TimeoutError:
        try:
            await ws.close(code=1001)
        except RuntimeError:
            pass
    except WebSocketDisconnect:
        pass
    finally:
        WS_SESSIONS.pop(ws, None)
        if user_id is not None:
            CHANNELS[user_id].discard(ws)
            if not any(sid == actor["session_id"] for sid in WS_SESSIONS.values()):
                await aim.clear_presence(user_id, actor["session_id"])
\nfrom .aim import router as aim_router\napp.include_router(aim_router)\n