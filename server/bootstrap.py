"""Single-use setup-code management for new Beacon installations.

Codes are stored in the persistent, container-owner-only data directory. The
HTTP API never returns a setup code. On first startup it is printed to the
private Dokploy container log so the server owner can claim the first admin.
"""
from __future__ import annotations

import hmac
import os
import secrets
import stat
from pathlib import Path


def code_path(db_path: str) -> Path:
    return Path(str(db_path) + ".setup-code")


def obtain_setup_code(db_path: str) -> str:
    """Create exactly once and preserve the token across pre-setup restarts."""
    path = code_path(db_path)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(fd, "w", encoding="ascii") as file:
            file.write(secrets.token_urlsafe(32) + "\n")
            file.flush()
            os.fsync(file.fileno())
    state = path.lstat()
    if not stat.S_ISREG(state.st_mode) or state.st_uid != os.getuid():
        raise RuntimeError("Invalid ownership/type for Beacon setup code file")
    path.chmod(0o600)
    token = path.read_text(encoding="ascii").strip()
    if len(token) < 32 or len(token) > 128:
        raise RuntimeError("Invalid Beacon setup code file")
    return token


def matches_setup_code(db_path: str, submitted: str) -> bool:
    """Constant-time verification; never creates a token from an HTTP call."""
    try:
        path = code_path(db_path)
        if not stat.S_ISREG(path.lstat().st_mode):
            return False
        code = path.read_text(encoding="ascii").strip()
    except (OSError, ValueError, UnicodeError):
        return False
    if not 32 <= len(code) <= 128:
        return False
    return hmac.compare_digest(code, submitted.strip())


def retire_setup_code(db_path: str) -> None:
    code_path(db_path).unlink(missing_ok=True)
