"""Portable tests for Windows integration selection and DPAPI roundtrip."""
import ast
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
    syntax = ast.parse(desktop)
    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module == "platform_integration"
        and any(alias.name == "notify" for alias in node.names)
        for node in ast.walk(syntax)
    ), "Desktop client must import the cross-platform notification adapter"
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "notify"
        and len(node.args) >= 2
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "Beacon"
        for node in ast.walk(syntax)
    ), "Desktop client must actually invoke notifications"
    integration = (MODULE.parent / "platform_integration.py").read_text(encoding="utf-8")
    assert "system_notice as windows_notice" in integration
    assert "return windows_notice(title, message)" in integration
    assert callable(module.system_notice)
