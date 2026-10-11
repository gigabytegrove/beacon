"""Keep distributable, docs and server versions aligned."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_documentation_and_platform_sources_exist():
    for relative in (
        "README.md", "CHANGELOG.md", "docs/INSTALL.md", "docs/DOKPLOY.md",
        "docs/API.md", "docs/ARCHITECTURE.md", "docs/SECURITY.md",
        "docs/TROUBLESHOOTING.md", "docs/DEVELOPMENT.md",
        "docs/RELEASE-CHECKLIST.md", "clients/desktop/README.md",
        "clients/android/README.md", "clients/desktop/linux/beacon.desktop",
        "clients/desktop/linux/install.sh", "clients/desktop/linux/uninstall.sh",
        "clients/desktop/platform_integration.py", "clients/desktop/win_integration.py",
        "clients/android/app/src/main/java/net/gigabytegrove/beacon/MainActivity.java",
        "clients/android/app/src/main/java/net/gigabytegrove/beacon/BeaconMonitorService.java",
        ".github/workflows/windows.yml", ".github/workflows/linux.yml",
        ".github/workflows/android.yml", "compose.dokploy.yaml",
        "clients/desktop-go/go.mod", "clients/desktop-go/README.md",
        "clients/desktop-go/cmd/beacon/main.go", "clients/desktop-go/cmd/beacon/chat.go",
        "clients/desktop-go/cmd/beacon/dialogs.go", "clients/desktop-go/cmd/beacon/assets/icon.svg",
        "clients/desktop-go/internal/beacon/api.go", "clients/desktop-go/internal/beacon/api_test.go",
    ):
        assert (ROOT / relative).is_file(), relative


def test_versions_and_server_registration():
    main = (ROOT / "server/main.py").read_text()
    android = (ROOT / "clients/android/app/build.gradle").read_text()
    workflow = (ROOT / ".github/workflows/windows.yml").read_text()
    linux = (ROOT / ".github/workflows/linux.yml").read_text()
    assert 'version="0.8.0"' in main
    assert "versionName '0.7.0'" in android
    assert "versionCode 7" in android
    assert "Beacon-Windows-0.8.0.exe" in workflow
    assert "Beacon-Linux-0.8.0.tar.gz" in linux
    assert '@app.get("/api/messages/search")' in main
    assert 'name: beacon-data' in (ROOT / "compose.dokploy.yaml").read_text()


def test_go_desktop_is_primary_and_not_python_packaged():
    desktop_module = (ROOT / "clients/desktop-go/go.mod").read_text()
    assert "fyne.io/fyne/v2" in desktop_module
    assert "github.com/zalando/go-keyring" in desktop_module
    windows = (ROOT / ".github/workflows/windows.yml").read_text()
    linux = (ROOT / ".github/workflows/linux.yml").read_text()
    for workflow in (windows, linux):
        assert "go build" in workflow
        assert "clients/desktop-go" in workflow
        assert "PyInstaller" not in workflow
        assert "beacon_desktop.py" not in workflow
    readme = (ROOT / "README.md").read_text()
    assert "do **not** need Python" in readme


def test_manual_builders_and_probe_are_separate_from_clients():
    root = ROOT
    for relative in (
        "scripts/build-desktop-windows.ps1",
        "scripts/build-desktop-linux.sh",
        "scripts/build-android-windows.ps1",
        "docs/BUILD-AND-TEST.md",
        "tools/beacon-probe/main.go",
        "tools/beacon-probe/README.md",
    ):
        assert (root / relative).is_file(), relative
    probe = (root / "tools/beacon-probe/main.go").read_text()
    assert "It is NOT the Beacon graphical instant messaging client." in probe
    for wf in ("windows.yml", "linux.yml"):
        source = (root / ".github/workflows" / wf).read_text()
        assert "scripts/build-desktop-" in source
        assert "PyInstaller" not in source
