"""Per-user AIM-style buddy groups, aliases and notification muting."""
import sqlite3

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, model_validator

router = APIRouter(prefix="/api")


def core():
    from . import main
    return main


def migrate(db: sqlite3.Connection):
    db.execute("""
        CREATE TABLE IF NOT EXISTS buddy_groups(
            id INTEGER PRIMARY KEY,
            owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name TEXT NOT NULL COLLATE NOCASE,
            created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')),
            UNIQUE(owner_id, name)
        )
    """)
    fields = {row["name"] for row in db.execute("PRAGMA table_info(buddies)")}
    if "group_id" not in fields:
        db.execute("ALTER TABLE buddies ADD COLUMN group_id INTEGER")
    if "nickname" not in fields:
        db.execute("ALTER TABLE buddies ADD COLUMN nickname TEXT NOT NULL DEFAULT ''")
    if "muted" not in fields:
        db.execute("ALTER TABLE buddies ADD COLUMN muted INTEGER NOT NULL DEFAULT 0")
    db.execute("CREATE INDEX IF NOT EXISTS idx_buddies_group ON buddies(owner_id,group_id)")


class GroupIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)


class BuddyEdit(BaseModel):
    nickname: str | None = Field(default=None, max_length=80)
    group_id: int | None = Field(default=None, ge=1)
    muted: bool | None = None

    @model_validator(mode="after")
    def at_least_one_field(self):
        if not self.model_fields_set:
            raise ValueError("Provide at least one buddy setting")
        return self


def normalized_group(name):
    clean = name.strip()
    if not clean or clean.casefold() == "buddies":
        raise HTTPException(422, "Enter a group name other than Buddies")
    return clean


def owner(request):
    m = core()
    return m.current(request)["id"]


@router.get("/groups")
def groups(request: Request):
    user_id = owner(request)
    m = core()
    with m.connection() as db:
        data = db.execute(
            "SELECT id,name FROM buddy_groups WHERE owner_id=? ORDER BY name COLLATE NOCASE",
            (user_id,)
        ).fetchall()
    return [dict(item) for item in data]


@router.post("/groups", status_code=201)
async def add_group(data: GroupIn, request: Request):
    user_id = owner(request)
    m = core()
    name = normalized_group(data.name)
    with m.LOCK, m.connection() as db:
        try:
            cursor = db.execute(
                "INSERT INTO buddy_groups(owner_id,name) VALUES(?,?)", (user_id, name)
            )
        except sqlite3.IntegrityError:
            raise HTTPException(409, "Group already exists")
        group_id = cursor.lastrowid
    return {"id": group_id, "name": name}


@router.patch("/groups/{group_id}")
async def rename_group(group_id: int, data: GroupIn, request: Request):
    user_id = owner(request)
    m = core()
    name = normalized_group(data.name)
    with m.LOCK, m.connection() as db:
        try:
            result = db.execute(
                "UPDATE buddy_groups SET name=? WHERE id=? AND owner_id=?",
                (name, group_id, user_id)
            )
        except sqlite3.IntegrityError:
            raise HTTPException(409, "Group already exists")
        if result.rowcount == 0:
            raise HTTPException(404, "Group not found")
    return {"id": group_id, "name": name}


@router.delete("/groups/{group_id}")
async def delete_group(group_id: int, request: Request):
    user_id = owner(request)
    m = core()
    with m.LOCK, m.connection() as db:
        if not db.execute(
            "SELECT 1 FROM buddy_groups WHERE id=? AND owner_id=?", (group_id, user_id)
        ).fetchone():
            raise HTTPException(404, "Group not found")
        # Preserve buddy relationships when a group is removed.
        db.execute(
            "UPDATE buddies SET group_id=NULL WHERE owner_id=? AND group_id=?",
            (user_id, group_id)
        )
        db.execute("DELETE FROM buddy_groups WHERE id=? AND owner_id=?", (group_id, user_id))
    return {"ok": True}


@router.patch("/buddies/{buddy_id}")
async def edit_buddy(buddy_id: int, data: BuddyEdit, request: Request):
    user_id = owner(request)
    m = core()
    updates = []
    args = []
    if "nickname" in data.model_fields_set:
        updates.append("nickname=?")
        args.append((data.nickname or "").strip())
    if "muted" in data.model_fields_set:
        if data.muted is None:
            raise HTTPException(422, "Muted must be true or false")
        updates.append("muted=?")
        args.append(int(data.muted))
    if "group_id" in data.model_fields_set:
        if data.group_id is not None:
            with m.connection() as db:
                if not db.execute(
                    "SELECT 1 FROM buddy_groups WHERE id=? AND owner_id=?",
                    (data.group_id, user_id)
                ).fetchone():
                    raise HTTPException(422, "Group does not belong to your account")
        updates.append("group_id=?")
        args.append(data.group_id)
    if not updates:
        raise HTTPException(422, "No updates provided")
    with m.LOCK, m.connection() as db:
        result = db.execute(
            "UPDATE buddies SET " + ",".join(updates) + " WHERE owner_id=? AND buddy_id=?",
            (*args, user_id, buddy_id)
        )
        if result.rowcount == 0:
            raise HTTPException(404, "Buddy not on your list")
    return {"ok": True}
