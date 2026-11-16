"""Portable tests for Windows integration selection and DPAPI roundtrip."""
import importlib.util
import sys
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "clients" / "desktop" / "win_integration.py"
spec = importlib.util.spec_from_file_location("beacon_win_integration", MODULE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_os_guard_and_protected_storage():
    if sys.platform == "win32":
        sample = b"beacon-opaque-session-test"
        assert module.unprotect(module.protect(sample)) == sample
    else:
        assert module.config_path() is None
        assert module.load_session() is None
        assert module.save_session("http://127.0.0.1:8765", "test-secret") is False
        try:
            module.protect(b"test")
        except OSError:
            pass
        else:
            raise AssertionError("DPAPI must reject unsupported platforms")


def test_source_entrypoints():
    desktop = (MODULE.parent / "beacon_desktop.py").read_text(encoding="utf-8")
    assert "self.restore_saved_session()" in desktop
    assert "self.ensure_tray()" in desktop
    assert "def close_window(self)" in desktop
    # Beacon uses the platform-neutral notify() adapter, which forwards to
    # Windows system_notice() and to notify-send on Linux.
    assert 'notify, create_tray' in desktop
    assert 'if notify("Beacon", text):' in desktop
    integration = (MODULE.parent / "platform_integration.py").read_text(encoding="utf-8")
    assert "system_notice as windows_notice" in integration
    assert "return windows_notice(title, message)" in integration
    assert callable(module.system_notice)
