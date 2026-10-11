"""AIM-inspired buddy list, profile, presence and transient typing APIs for Beacon."""
import asyncio
import base64
import binascii
import io
import time
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from PIL import Image, ImageOps, UnidentifiedImageError

Image.MAX_IMAGE_PIXELS = 4_000_000

router = APIRouter(prefix="/api")
PRESENCE_TTL = 55
TYPING = {}
LAST_TYPING = defaultdict(float)


def core():
    from . import main
    return main


def presence(user_id):
    m = core()
    now = int(time.time())
    with m.connection() as db:
        rows = db.execute(
            "SELECT presence FROM sessions WHERE user_id=? AND expires_at>? AND last_seen>?",
            (user_id, now, now - PRESENCE_TTL)
        ).fetchall()
    if not rows:
        return "offline"
    values = [r["presence"] for r in rows]
    for value in ("available", "busy", "away"):
        if value in values:
            return value
    return "offline"


async def notify_presence(user_id, old):
    new = presence(user_id)
    if old == new:
        return
    m = core()
    with m.connection() as db:
        watchers = db.execute("SELECT owner_id FROM buddies WHERE buddy_id=?", (user_id,)).fetchall()
    event = {"type": "presence", "user_id": user_id, "status": new}
    for row in watchers:
        await m.publish(row["owner_id"], event)


async def set_presence(user_id, session_id, status):
    if status not in ("available", "away", "busy"):
        raise HTTPException(422, "Invalid presence")
    m = core()
    old = presence(user_id)
    with m.LOCK, m.connection() as db:
        db.execute("UPDATE sessions SET presence=?,last_seen=? WHERE user_id=? AND id=?",
                   (status, int(time.time()), user_id, session_id))
    await notify_presence(user_id, old)


async def touch_presence(user_id, session_id):
    m = core()
    old = presence(user_id)
    with m.LOCK, m.connection() as db:
        db.execute("UPDATE sessions SET last_seen=? WHERE user_id=? AND id=?",
                   (int(time.time()), user_id, session_id))
    await notify_presence(user_id, old)


async def clear_presence(user_id, session_id):
    m = core()
    old = presence(user_id)
    with m.LOCK, m.connection() as db:
        db.execute("UPDATE sessions SET last_seen=0 WHERE user_id=? AND id=?", (user_id, session_id))
    await notify_presence(user_id, old)


async def presence_sweeper():
    while True:
        await asyncio.sleep(15)
        m = core()
        cutoff = int(time.time()) - PRESENCE_TTL
        with m.LOCK, m.connection() as db:
            expired = db.execute(
                "SELECT DISTINCT user_id FROM sessions WHERE last_seen>0 AND last_seen<=?",
                (cutoff,)
            ).fetchall()
            previous = {r["user_id"]: presence(r["user_id"]) for r in expired}
            db.execute("UPDATE sessions SET last_seen=0 WHERE last_seen>0 AND last_seen<=?", (cutoff,))
        for user_id, old in previous.items():
            await notify_presence(user_id, old)


async def send_typing(user_id, recipient_id, active):
    m = core()
    if not isinstance(recipient_id, int) or recipient_id == user_id:
        return
    with m.connection() as db:
        if not db.execute("SELECT 1 FROM users WHERE id=?", (recipient_id,)).fetchone():
            return
    now = time.monotonic()
    key = (user_id, recipient_id)
    if active and now - LAST_TYPING[key] < 0.8:
        return
    LAST_TYPING[key] = now
    if active:
        TYPING[key] = now + 5
    else:
        TYPING.pop(key, None)
    await m.publish(recipient_id, {"type": "typing", "user_id": user_id, "active": active})


class PresenceUpdate(BaseModel):
    status: str = Field(pattern="^(available|away|busy)$")


class ProfileUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    status_text: str = Field(max_length=140)


class AvatarUpload(BaseModel):
    image_base64: str = Field(max_length=360000)
    mime_type: str = Field(pattern="^image/(png|jpeg|webp)$")


class TypingUpdate(BaseModel):
    active: bool


class ReadUpdate(BaseModel):
    through_id: int = Field(ge=0)


def attach_presence(db, rows):
    """Resolve presence for an entire roster in one SQLite query, not N queries."""
    items = [dict(row) for row in rows]
    if not items:
        return items
    user_ids = [item["id"] for item in items]
    now = int(time.time())
    statuses = {}
    # SQLite supports at least 999 bind parameters even on older deployments.
    for offset in range(0, len(user_ids), 400):
        chunk = user_ids[offset:offset + 400]
        placeholders = ",".join("?" for _ in chunk)
        active = db.execute(
            "SELECT user_id,presence FROM sessions WHERE user_id IN (" + placeholders +
            ") AND expires_at>? AND last_seen>?",
            (*chunk, now, now - PRESENCE_TTL),
        ).fetchall()
        for session in active:
            candidate = session["presence"]
            previous = statuses.get(session["user_id"], "offline")
            priority = {"offline": 0, "away": 1, "busy": 2, "available": 3}
            if priority.get(candidate, 0) > priority.get(previous, 0):
                statuses[session["user_id"]] = candidate
    for item in items:
        item["presence"] = statuses.get(item["id"], "offline")
    return items


@router.get("/directory")
def directory(request: Request):
    m = core()
    actor = m.current(request)
    with m.connection() as db:
        rows = db.execute(
            "SELECT id,username,display_name,status_text,avatar FROM users WHERE id<>? ORDER BY display_name",
            (actor["id"],)
        ).fetchall()
        return attach_presence(db, rows)


@router.get("/buddies")
def buddies(request: Request):
    m = core()
    actor = m.current(request)
    with m.connection() as db:
        rows = db.execute("""
        SELECT u.id,u.username,u.display_name,u.avatar,u.status_text,
               b.nickname,b.group_id,b.muted,COALESCE(g.name,'Buddies') AS group_name,
               (SELECT COUNT(*) FROM messages msg WHERE msg.sender_id=u.id
                AND msg.recipient_id=? AND msg.id>COALESCE(
                  (SELECT last_read_id FROM read_cursors
                   WHERE user_id=? AND peer_id=u.id),0)) AS unread_count
        FROM buddies b JOIN users u ON u.id=b.buddy_id
        LEFT JOIN buddy_groups g ON g.owner_id=b.owner_id AND g.id=b.group_id
        WHERE b.owner_id=? ORDER BY group_name COLLATE NOCASE,u.display_name
        """, (actor["id"], actor["id"], actor["id"])).fetchall()
        return attach_presence(db, rows)


@router.post("/buddies/{buddy_id}", status_code=201)
async def add_buddy(buddy_id: int, request: Request):
    m = core()
    actor = m.current(request)
    if buddy_id == actor["id"]:
        raise HTTPException(422, "You cannot add yourself")
    with m.LOCK, m.connection() as db:
        if not db.execute("SELECT 1 FROM users WHERE id=?", (buddy_id,)).fetchone():
            raise HTTPException(404, "User not found")
        db.execute("INSERT OR IGNORE INTO buddies(owner_id,buddy_id) VALUES (?,?)",
                   (actor["id"],buddy_id))
    return {"ok": True}


@router.delete("/buddies/{buddy_id}")
async def remove_buddy(buddy_id: int, request: Request):
    m = core()
    actor = m.current(request)
    with m.LOCK, m.connection() as db:
        db.execute("DELETE FROM buddies WHERE owner_id=? AND buddy_id=?", (actor["id"],buddy_id))
    return {"ok": True}


@router.put("/me/profile")
async def profile(data: ProfileUpdate, request: Request):
    m = core()
    actor = m.current(request)
    if not data.display_name.strip():
        raise HTTPException(422, "Display name must not be empty")
    with m.LOCK, m.connection() as db:
        db.execute("UPDATE users SET display_name=?,status_text=? WHERE id=?",
                   (data.display_name.strip(),data.status_text.strip(),actor["id"]))
    await profile_changed(actor["id"])
    return {"ok": True}


async def profile_changed(user_id):
    m = core()
    with m.connection() as db:
        watchers = db.execute("SELECT owner_id FROM buddies WHERE buddy_id=?", (user_id,)).fetchall()
    for row in watchers:
        await m.publish(row["owner_id"], {"type": "profile", "user_id": user_id})


@router.post("/me/avatar")
async def avatar(data: AvatarUpload, request: Request):
    m = core()
    actor = m.current(request)
    try:
        raw = base64.b64decode(data.image_base64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(422, "Invalid image data")
    if len(raw) > 192 * 1024 or len(raw) < 12:
        raise HTTPException(413, "Photo must be under 192 KiB")
    formats = {"image/png": "PNG", "image/jpeg": "JPEG", "image/webp": "WEBP"}
    try:
        with Image.open(io.BytesIO(raw)) as source:
            if source.format != formats[data.mime_type]:
                raise HTTPException(422, "Photo content does not match its declared format")
            if source.width * source.height > 4_000_000:
                raise HTTPException(413, "Photo resolution exceeds 4 megapixels")
            source.load()
            photo = ImageOps.exif_transpose(source).convert("RGB")
            photo.thumbnail((256, 256), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            photo.save(output, format="JPEG", quality=84, optimize=True)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise HTTPException(422, "Invalid or damaged image file")
    cleaned = output.getvalue()
    if len(cleaned) > 192 * 1024:
        raise HTTPException(413, "Processed photo is too large")
    uri = "data:image/jpeg;base64," + base64.b64encode(cleaned).decode("ascii")
    with m.LOCK, m.connection() as db:
        db.execute("UPDATE users SET avatar=? WHERE id=?", (uri, actor["id"]))
    await profile_changed(actor["id"])
    return {"ok": True}


@router.post("/presence")
async def heartbeat(data: PresenceUpdate, request: Request):
    m = core()
    actor = m.current(request)
    await set_presence(actor["id"], actor["session_id"], data.status)
    return {"status": presence(actor["id"])}


@router.post("/typing/{recipient_id}")
async def typing(recipient_id: int, data: TypingUpdate, request: Request):
    m = core()
    actor = m.current(request)
    await send_typing(actor["id"], recipient_id, data.active)
    return {"ok": True}


@router.get("/typing/{peer_id}")
def typing_state(peer_id: int, request: Request):
    m = core()
    actor = m.current(request)
    return {"active": TYPING.get((peer_id, actor["id"]), 0) > time.monotonic()}


@router.get("/conversations")
def conversations(request: Request):
    m = core()
    actor = m.current(request)
    with m.connection() as db:
        rows = db.execute("""
        SELECT u.id AS peer_id,u.display_name,
          (SELECT COUNT(*) FROM messages msg WHERE msg.sender_id=u.id AND msg.recipient_id=?
           AND msg.id>COALESCE((SELECT last_read_id FROM read_cursors
            WHERE user_id=? AND peer_id=u.id),0)) AS unread_count
        FROM users u WHERE u.id<>? ORDER BY u.display_name
        """,(actor["id"],actor["id"],actor["id"])).fetchall()
    return [dict(row) for row in rows]


@router.post("/conversations/{peer_id}/read")
async def mark_read(peer_id: int, data: ReadUpdate, request: Request):
    m = core()
    actor = m.current(request)
    with m.LOCK, m.connection() as db:
        if not db.execute("SELECT 1 FROM users WHERE id=?", (peer_id,)).fetchone():
            raise HTTPException(404, "User not found")
        last = db.execute(
            "SELECT COALESCE(MAX(id),0) FROM messages WHERE sender_id=? AND recipient_id=? AND id<=?",
            (peer_id,actor["id"],data.through_id)
        ).fetchone()[0]
        db.execute("""
        INSERT INTO read_cursors(user_id,peer_id,last_read_id) VALUES(?,?,?)
        ON CONFLICT(user_id,peer_id)
        DO UPDATE SET last_read_id=MAX(last_read_id,excluded.last_read_id)
        """,(actor["id"],peer_id,last))
    await m.publish(actor["id"], {"type":"read_updated","peer_id":peer_id})
    return {"ok":True,"through_id":last}


@router.get("/events/latest")
def latest_event(request: Request):
    """Last persisted message visible to this user, for first-run device cursor seeding."""
    m = core()
    actor = m.current(request)
    with m.connection() as db:
        latest = db.execute(
            "SELECT COALESCE(MAX(id),0) FROM messages WHERE sender_id=? OR recipient_id=?",
            (actor["id"], actor["id"])
        ).fetchone()[0]
    return {"last_message_id": latest}


@router.get("/events")
def events(request: Request, after: int = 0, limit: int = 200):
    m = core()
    actor = m.current(request)
    if after < 0 or not 1 <= limit <= 500:
        raise HTTPException(422, "Invalid cursor or limit")
    with m.connection() as db:
        rows = db.execute("""
        SELECT id,sender_id,recipient_id,body,created_at FROM messages
        WHERE id>? AND (sender_id=? OR recipient_id=?)
        ORDER BY id LIMIT ?
        """,(after,actor["id"],actor["id"],limit)).fetchall()
    return {"events":[dict(row) for row in rows],
            "next_cursor": rows[-1]["id"] if rows else after}
