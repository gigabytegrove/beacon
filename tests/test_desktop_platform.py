"""Platform adapter contracts without requiring a graphical display."""
import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "clients" / "desktop"
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("beacon_platform", ROOT / "platform_integration.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_preferences_roundtrip_on_linux(monkeypatch, tmp_path):
    monkeypatch.setattr(module, "is_linux", lambda: True)
    monkeypatch.setattr(module, "is_windows", lambda: False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert module.save_preferences({"sound_alerts": False, "auto_open_im": True})
    assert module.load_preferences() == {"sound_alerts": False, "auto_open_im": True}
    written = (tmp_path / "beacon" / "preferences.json").read_text()
    assert "token" not in written
    assert "password" not in written


def test_never_fallback_to_plaintext_session(monkeypatch):
    monkeypatch.setattr(module, "is_windows", lambda: False)
    monkeypatch.setattr(module, "is_linux", lambda: True)
    monkeypatch.setattr(module, "_keyring", lambda: None)
    assert module.load_session() is None
    assert module.save_session("https://beacon.lan", "secret-token") is False
    module.clear_session()


def test_client_wires_all_desktop_features():
    source = (ROOT / "beacon_desktop.py").read_text("utf-8")
    for expected in ("def edit_profile(", "def upload_avatar(", "def change_password(", "def manage_devices(", "def search_history(",
                     "def ensure_tray(", "load_preferences()", "def restore_saved_session("):
        assert expected in source
