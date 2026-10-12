"""Native supervisor tests without Docker or a live network connection."""
import io
import json
from pathlib import Path

from server import launcher


def test_release_validation_rejects_corrupt_and_untracked_versions(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "DATA", tmp_path)
    assert launcher._release("not-a-commit") is None
    revision = "a" * 40
    folder = tmp_path / "releases" / revision
    folder.mkdir(parents=True)
    assert launcher._release(revision) is None
    (folder / "server").mkdir()
    (folder / "server" / "main.py").write_text("app = object()\n")
    launcher._write(folder / "release.json", {"revision": "b"*40, "version": "0.9.1"})
    assert launcher._release(revision) is None
    launcher._write(folder / "release.json", {"revision": revision, "version": "0.9.1"})
    assert launcher._release(revision) == folder


def test_supervisor_launches_staged_code_as_selected_import_root(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "DATA", tmp_path)
    revision = "a" * 40
    folder = tmp_path / "releases" / revision
    (folder / "server").mkdir(parents=True)
    (folder / "server" / "main.py").write_text("x = 1\n")
    launcher._write(folder / "release.json", {"revision": revision, "version": "0.9.1"})
    spawned = []

    class FakeProcess:
        def poll(self):
            return None

    def create_process(command, cwd=None, env=None):
        spawned.append((command, cwd, env))
        return FakeProcess()

    monkeypatch.setattr(launcher.subprocess, "Popen", create_process)
    process = launcher._running(revision)
    assert process is not None
    command, cwd, env = spawned[-1]
    assert command[0] == launcher.sys.executable
    assert command[1:3] == ["-m", "uvicorn"]
    assert cwd == str(folder)
    assert env["BEACON_RUNTIME_REVISION"] == revision
    assert env["BEACON_RUNTIME_VERSION"] == "0.9.1"


def test_health_check_requires_running_revision_match(monkeypatch):
    class FakeProcess:
        def poll(self):
            return None

    class Response:
        status = 200
        def __init__(self, revision):
            self.payload = io.BytesIO(json.dumps({
                "status": "ok", "revision": revision,
            }).encode())
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass
        def read(self, length=-1):
            return self.payload.read(length)

    wanted = "a" * 40
    monkeypatch.setattr(launcher, "stop_requested", False)
    monkeypatch.setattr(launcher, "urlopen", lambda *args, **kwargs: Response(wanted))
    assert launcher._healthy(FakeProcess(), wanted, deadline=1) is True
    assert launcher._healthy(FakeProcess(), "b" * 40, deadline=0.01) is False


def test_pending_and_active_files_survive_process_recreation(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "DATA", tmp_path)
    active = tmp_path / "current.json"
    launcher._write(active, {"revision": "a"*40, "previous": ""})
    assert launcher._read(active)["previous"] == ""
    assert launcher._read(active)["revision"] == "a"*40
    assert launcher._read(tmp_path / "missing.json") == {}
