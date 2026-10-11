"""Windows-only OS integrations; Linux retains memory-only sessions."""
import ctypes
import ctypes.wintypes as wt
import json
import os
import sys
from pathlib import Path


def is_windows():
    return sys.platform == "win32"


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _blob(data):
    buffer = ctypes.create_string_buffer(data)
    blob = DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    return blob, buffer


def protect(data):
    """Encrypt token using current Windows user's DPAPI keys."""
    if not is_windows():
        raise OSError("DPAPI is only available on Windows")
    source, backing = _blob(data)
    target = DATA_BLOB()
    crypt = ctypes.windll.crypt32
    crypt.CryptProtectData.argtypes = [ctypes.POINTER(DATA_BLOB), wt.LPCWSTR,
                                      ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                                      wt.DWORD, ctypes.POINTER(DATA_BLOB)]
    crypt.CryptProtectData.restype = wt.BOOL
    if not crypt.CryptProtectData(ctypes.byref(source), "Beacon session", None, None,
                                  None, 0x1, ctypes.byref(target)):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(target.pbData, target.cbData)
    finally:
        local_free = ctypes.windll.kernel32.LocalFree
        local_free.argtypes = [ctypes.c_void_p]
        local_free.restype = ctypes.c_void_p
        local_free(target.pbData)


def unprotect(data):
    if not is_windows():
        raise OSError("DPAPI is only available on Windows")
    source, backing = _blob(data)
    target = DATA_BLOB()
    crypt = ctypes.windll.crypt32
    crypt.CryptUnprotectData.argtypes = [ctypes.POINTER(DATA_BLOB), ctypes.c_void_p,
                                        ctypes.c_void_p, ctypes.c_void_p,
                                        ctypes.c_void_p, wt.DWORD, ctypes.POINTER(DATA_BLOB)]
    crypt.CryptUnprotectData.restype = wt.BOOL
    if not crypt.CryptUnprotectData(ctypes.byref(source), None, None, None,
                                    None, 0x1, ctypes.byref(target)):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(target.pbData, target.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(target.pbData)


def config_path():
    if not is_windows():
        return None
    root = os.environ.get("LOCALAPPDATA")
    if not root:
        return None
    return Path(root) / "Beacon" / "session.bin"


def save_session(server, token):
    path = config_path()
    if path is None:
        return False
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps({"server": server, "token": token}).encode("utf-8")
        target = path.with_suffix(".tmp")
        target.write_bytes(protect(data))
        target.replace(path)
        return True
    except (OSError, ValueError):
        return False


def load_session():
    path = config_path()
    if path is None or not path.exists():
        return None
    try:
        payload = json.loads(unprotect(path.read_bytes()).decode("utf-8"))
        if not isinstance(payload, dict):
            return None
        if not isinstance(payload.get("server"), str) or not isinstance(payload.get("token"), str):
            return None
        return payload
    except (OSError, ValueError, UnicodeError):
        return None


def clear_session():
    path = config_path()
    if path is not None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def tray_icon(on_open, on_quit):
    """Return optional Windows tray icon; callbacks run on the tray thread."""
    if not is_windows():
        return None
    try:
        import pystray
        from PIL import Image, ImageDraw
        picture = Image.new("RGB", (64, 64), (23, 55, 84))
        draw = ImageDraw.Draw(picture)
        draw.ellipse((25, 5, 39, 19), fill=(101, 208, 255))
        draw.rectangle((28, 23, 36, 54), fill=(101, 208, 255))
        draw.arc((7, 7, 57, 52), 200, 340, fill=(101, 208, 255), width=5)
        menu = pystray.Menu(
            pystray.MenuItem("Open Beacon", lambda *_: on_open(), default=True),
            pystray.MenuItem("Quit Beacon", lambda *_: on_quit()),
        )
        icon = pystray.Icon("Beacon", picture, "Beacon Messenger", menu)
        icon.run_detached()
        return icon
    except Exception:
        return None


def system_notice(title, message):
    if not is_windows():
        return False
    try:
        from winotify import Notification
        alert = Notification(app_id="Beacon Messenger", title=title, msg=message[:180],
                             duration="short")
        alert.show()
        return True
    except Exception:
        return False
