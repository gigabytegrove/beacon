import asyncio
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
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
SETUP_ATTEMPTS = defaultdict(deque)
CHANNELS: dict[int, set[WebSocket]] = defaultdict(set)
WS_SESSIONS: dict[WebSocket, int] = {}
USERNAME = re.compile(r"^[a-zA-Z0-9_.-]{3,32}$")


@contextmanager
def connection():
    """One SQLite connection per unit of work, committed/rolled back and closed."""
    db = sqlite3.connect(DB, timeout=10)
    try:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=10000")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
    finally:
        db.close()


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
        CREATE TABLE IF NOT EXISTS server_settings(
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
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
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_presence "
            "ON sessions(user_id,expires_at,last_seen,presence)"
        )
        from .social import migrate
        migrate(db)
        # Existing installations are never reset. A password supplied by older
        # deployments remains supported; fresh installations use the wizard.
        from .bootstrap import obtain_setup_code, retire_setup_code
        if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            password = os.getenv("BEACON_ADMIN_PASSWORD", "")
            if password:
                username = os.getenv("BEACON_ADMIN_USERNAME", "admin")
                if not USERNAME.fullmatch(username) or len(password) < 12 or password == "REPLACE_WITH_A_LONG_RANDOM_PASSWORD":
                    raise RuntimeError("Invalid legacy BEACON_ADMIN_USERNAME or BEACON_ADMIN_PASSWORD")
                db.execute(
                    "INSERT INTO users(username,display_name,password_hash,is_admin,created_at) VALUES (?,?,?,?,?)",
                    (username, username, password_hash(password), 1, int(time.time())),
                )
                retire_setup_code(DB)
            else:
                code = obtain_setup_code(DB)
                print("", flush=True)
                print("===== BEACON FIRST-RUN ADMIN SETUP =====", flush=True)
                print("Open Beacon in your browser and choose Create administrator.", flush=True)
                print("SETUP CODE: " + code, flush=True)
                print("Copy this one-time code into the setup wizard.", flush=True)
                print("Only share this code with the person configuring Beacon.", flush=True)
                print("========================================", flush=True)
        else:
            retire_setup_code(DB)
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


app = FastAPI(title="Beacon", version=os.getenv("BEACON_VERSION", "0.8.5"), lifespan=lifespan)


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
    username: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=256)
    device_name: str = Field(min_length=1, max_length=80)


class FirstRunAdmin(BaseModel):
    setup_code: str = Field(min_length=16, max_length=128)
    username: str = Field(min_length=3, max_length=32)
    display_name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=12, max_length=256)


class NewUser(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=12, max_length=256)
    display_name: str = Field(min_length=1, max_length=80) = Field(min_length=1, max_length=80)


class ChangePassword(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


class NewMessage(BaseModel):
    recipient_id: int
    body: str = Field(min_length=1, max_length=4000)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/setup/status")
def setup_status():
    """Expose only whether setup is needed, never the private setup code."""
    with LOCK, connection() as db:
        required = db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
    return {"setup_required": required}


@app.post("/api/setup", status_code=201)
def first_run_setup(data: FirstRunAdmin, request: Request):
    """Claim an empty installation using the code from private Dokploy logs.

    A one-time claim always precedes normal login; setup never opens again once
    any account exists in the persistent database.
    """
    from .bootstrap import matches_setup_code, retire_setup_code
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    if not USERNAME.fullmatch(data.username):
        raise HTTPException(422, "Username must be 3-32 letters, numbers, _, . or -")
    if not data.display_name.strip():
        raise HTTPException(422, "Display name cannot be empty")
    if len(data.password.strip()) < 12:
        raise HTTPException(422, "Choose a password of at least 12 characters")
    with LOCK:
        attempts = SETUP_ATTEMPTS[ip]
        while attempts and attempts[0] < now - 900:
            attempts.popleft()
        with connection() as db:
            # BEGIN IMMEDIATE serializes first-user claims across processes.
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM users LIMIT 1").fetchone():
                raise HTTPException(409, "Beacon is already configured; sign in instead")
            if len(attempts) >= 5:
                raise HTTPException(429, "Too many setup attempts; try again later")
            if not matches_setup_code(DB, data.setup_code):
                attempts.append(now)
                raise HTTPException(403, "Incorrect setup code. Check the Dokploy Beacon logs.")
            db.execute(
                "INSERT INTO users(username,display_name,password_hash,is_admin,created_at) VALUES (?,?,?,?,?)",
                (data.username, data.display_name.strip(), password_hash(data.password), 1, int(time.time())),
            )
        attempts.clear()
        retire_setup_code(DB)
    return {"ok": True, "username": data.username, "message": "Administrator created. Sign in to Beacon."}


@app.get("/")
def home():
    return FileResponse(Path(__file__).parent / "static" / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/chat/{peer_id}")
def chat_window(peer_id: int):
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
    from .aim import presence, notify_presence
    old_presence = presence(user["id"])
    with LOCK, connection() as db:
        db.execute("DELETE FROM sessions WHERE id=? AND user_id=?", (user["session_id"], user["id"]))
    await disconnect_session(user["session_id"])
    await notify_presence(user["id"], old_presence)
    return {"ok": True}


@app.get("/api/me")
def me(request: Request):
    return current(request)


@app.get("/api/users")
def users(request: Request):
    current(request)
    with connection() as db:
        rows = db.execute("SELECT id,username,display_name,status_text,avatar FROM users ORDER BY display_name").fetchall()
    return [dict(row) for row in rows]


@app.post("/api/admin/users", status_code=201)
def create_user(data: NewUser, request: Request):
    actor = current(request)
    if not actor["is_admin"]:
        raise HTTPException(403, "Administrator required")
    if not USERNAME.fullmatch(data.username):
        raise HTTPException(422, "Username must be 3-32 letters, digits, _, . or -")
    if not data.display_name.strip():
        raise HTTPException(422, "Display name must not be empty")
    with LOCK, connection() as db:
        if db.execute("SELECT 1 FROM users WHERE username=? COLLATE NOCASE", (data.username,)).fetchone():
            raise HTTPException(409, "Username already exists")
        try:
            result = db.execute(
                "INSERT INTO users(username,display_name,password_hash,created_at) VALUES (?,?,?,?)",
                (data.username, data.display_name.strip(), password_hash(data.password), int(time.time())),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(409, "Username already exists")
    return {"id": result.lastrowid, "username": data.username, "display_name": data.display_name.strip(), "role": "member"}


@app.post("/api/me/password")
async def change_password(data: ChangePassword, request: Request):
    actor = current(request)
    if hmac.compare_digest(data.current_password, data.new_password):
        raise HTTPException(422, "New password must be different")
    with LOCK, connection() as db:
        existing = db.execute(
            "SELECT password_hash FROM users WHERE id=?", (actor["id"],)
        ).fetchone()
        if not existing or not verify_password(data.current_password, existing["password_hash"]):
            raise HTTPException(403, "Incorrect current password")
        db.execute("UPDATE users SET password_hash=? WHERE id=?",
                   (password_hash(data.new_password), actor["id"]))
        revoked = [row["id"] for row in db.execute(
            "SELECT id FROM sessions WHERE user_id=? AND id<>?",
            (actor["id"], actor["session_id"])
        )]
        db.execute("DELETE FROM sessions WHERE user_id=? AND id<>?",
                   (actor["id"], actor["session_id"]))
    for session_id in revoked:
        await disconnect_session(session_id)
    return {"ok": True, "other_sessions_revoked": len(revoked)}


@app.post("/api/sessions/revoke-others")
async def revoke_other_sessions(request: Request):
    actor = current(request)
    with LOCK, connection() as db:
        revoked = [row["id"] for row in db.execute(
            "SELECT id FROM sessions WHERE user_id=? AND id<>?",
            (actor["id"], actor["session_id"])
        )]
        db.execute("DELETE FROM sessions WHERE user_id=? AND id<>?",
                   (actor["id"], actor["session_id"]))
    for session_id in revoked:
        await disconnect_session(session_id)
    return {"ok": True, "revoked": len(revoked)}


@app.get("/api/sessions")
def sessions(request: Request):
    actor = current(request)
    with connection() as db:
        rows = db.execute("SELECT id,device_name,created_at,expires_at FROM sessions WHERE user_id=? AND expires_at>? ORDER BY id DESC", (actor["id"], int(time.time()))).fetchall()
    return [dict(row) | {"current": row["id"] == actor["session_id"]} for row in rows]


@app.delete("/api/sessions/{session_id}")
async def revoke_session(session_id: int, request: Request):
    actor = current(request)
    from .aim import presence, notify_presence
    old_presence = presence(actor["id"])
    with LOCK, connection() as db:
        result = db.execute("DELETE FROM sessions WHERE id=? AND user_id=?", (session_id, actor["id"]))
    if not result.rowcount:
        raise HTTPException(404, "Session not found")
    await disconnect_session(session_id)
    await notify_presence(actor["id"], old_presence)
    return {"ok": True}


@app.get("/api/messages/search")
def search_messages(request: Request, q: str, peer_id: int | None = None, limit: int = 50):
    """Authenticated server-side text search across this user's conversations."""
    actor = current(request)
    query = q.strip()
    if not 2 <= len(query) <= 100 or not 1 <= limit <= 100:
        raise HTTPException(422, "Search requires 2-100 characters and limit 1-100")
    if peer_id is not None:
        with connection() as db:
            if peer_id == actor["id"] or not db.execute("SELECT 1 FROM users WHERE id=?", (peer_id,)).fetchone():
                raise HTTPException(404, "Conversation not found")
    # Escape wildcards so input text is treated literally instead of a pattern.
    pattern = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    with connection() as db:
        rows = db.execute("""
          SELECT id,sender_id,recipient_id,body,created_at FROM messages
          WHERE (sender_id=:user OR recipient_id=:user)
          AND body LIKE :pattern ESCAPE '\\'
          AND (:peer IS NULL OR
              (sender_id=:user AND recipient_id=:peer) OR
              (sender_id=:peer AND recipient_id=:user))
          ORDER BY id DESC LIMIT :limit
        """, {"user": actor["id"], "pattern": pattern, "peer": peer_id, "limit": limit}).fetchall()
    return [dict(row) for row in rows]


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
        with connection() as db:
            saved = db.execute("SELECT presence FROM sessions WHERE id=?", (actor["session_id"],)).fetchone()
        await aim.set_presence(user_id, actor["session_id"], saved["presence"] if saved else "available")
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
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        WS_SESSIONS.pop(ws, None)
        if user_id is not None:
            CHANNELS[user_id].discard(ws)
            if not any(sid == actor["session_id"] for sid in WS_SESSIONS.values()):
                await aim.clear_presence(user_id, actor["session_id"])

from .aim import router as aim_router
app.include_router(aim_router)

from .social import router as social_router
app.include_router(social_router)

# Management API for the server web control center.
from .admin import register as register_admin_routes
register_admin_routes(app, current=current, connection=connection, lock=LOCK,
                      hash_password=password_hash, disconnect_session=disconnect_session)

# Deployments are initiated by Dokploy, never by attaching a Docker socket.
from .update_control import register as register_update_routes

def authorize_server_update(request: Request):
    actor = current(request)
    if not actor["is_admin"]:
        raise HTTPException(403, "Administrator access required")
    return actor

register_update_routes(app, administrator=authorize_server_update)
