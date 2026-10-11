"""Optional Windows and Linux desktop integration. Never stores plaintext bearer tokens."""
import json
import os
import subprocess
import sys
from pathlib import Path

from win_integration import (
    clear_session as clear_windows_session,
    is_windows,
    load_session as load_windows_session,
    save_session as save_windows_session,
    system_notice as windows_notice,
    tray_icon as windows_tray,
)
APP_ID = "net.gigabytegrove.beacon"


def is_linux():
    return sys.platform.startswith("linux")


def _keyring():
    if not is_linux():
        return None
    try:
        import keyring
        from keyring.backends.fail import Keyring as FailingBackend
        if isinstance(keyring.get_keyring(), FailingBackend):
            return None
        return keyring
    except (ImportError, RuntimeError, ValueError):
        return None


def _config_directory():
    if is_linux():
        return Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "beacon"
    if is_windows():
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Beacon"
    return None


def save_session(server, token):
    """Windows uses DPAPI; Linux uses system keyring, never plaintext files."""
    if is_windows():
        return save_windows_session(server, token)
    backend = _keyring()
    if backend is None:
        return False
    try:
        backend.set_password(APP_ID, "session", json.dumps({"server": server, "token": token}))
        return True
    except Exception:
        return False


def load_session():
    if is_windows():
        return load_windows_session()
    backend = _keyring()
    if backend is None:
        return None
    try:
        encoded = backend.get_password(APP_ID, "session")
        value = json.loads(encoded) if encoded else None
        if isinstance(value, dict) and isinstance(value.get("server"), str) and isinstance(value.get("token"), str):
            return value
    except Exception:
        pass
    return None


def clear_session():
    if is_windows():
        clear_windows_session()
    elif is_linux():
        backend = _keyring()
        if backend is not None:
            try:
                backend.delete_password(APP_ID, "session")
            except Exception:
                pass


def notify(title, message):
    if is_windows():
        return windows_notice(title, message)
    if is_linux():
        try:
            subprocess.Popen(
                ["notify-send", "--app-name=Beacon", "--expire-time=5500", title[:100], message[:300]],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True
            )
            return True
        except (OSError, ValueError):
            return False
    return False


def create_tray(on_open, on_quit):
    if is_windows():
        return windows_tray(on_open, on_quit)
    if not is_linux():
        return None
    try:
        import pystray
        from PIL import Image, ImageDraw
        picture = Image.new("RGB", (64, 64), (23, 55, 84))
        draw = ImageDraw.Draw(picture)
        draw.ellipse((25, 5, 39, 19), fill=(101, 208, 255))
        draw.rectangle((28, 23, 36, 54), fill=(101, 208, 255))
        menu = pystray.Menu(
            pystray.MenuItem("Open Beacon", lambda *_: on_open(), default=True),
            pystray.MenuItem("Quit Beacon", lambda *_: on_quit()),
        )
        icon = pystray.Icon("Beacon", picture, "Beacon Messenger", menu)
        icon.run_detached()
        return icon
    except Exception:
        return None


def load_preferences():
    path = _config_directory()
    if path is None:
        return {}
    try:
        value = json.loads((path / "preferences.json").read_text("utf-8"))
        if isinstance(value, dict):
            return {key: value[key] for key in ("sound_alerts", "auto_open_im")
                    if key in value and isinstance(value[key], bool)}
    except (OSError, ValueError, TypeError):
        pass
    return {}


def save_preferences(settings):
    path = _config_directory()
    if path is None:
        return False
    try:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        tmp = path / "preferences.tmp"
        tmp.write_text(json.dumps({
            "sound_alerts": bool(settings.get("sound_alerts", True)),
            "auto_open_im": bool(settings.get("auto_open_im", True)),
        }), "utf-8")
        if is_linux():
            os.chmod(tmp, 0o600)
        tmp.replace(path / "preferences.json")
        return True
    except OSError:
        return False
