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
    ):
        assert (ROOT / relative).is_file(), relative


def test_versions_and_server_registration():
    main = (ROOT / "server/main.py").read_text()
    android = (ROOT / "clients/android/app/build.gradle").read_text()
    workflow = (ROOT / ".github/workflows/windows.yml").read_text()
    linux = (ROOT / ".github/workflows/linux.yml").read_text()
    assert 'version="0.7.0"' in main
    assert "versionName '0.7.0'" in android
    assert "versionCode 7" in android
    assert "Beacon-Windows-0.7.0.exe" in workflow
    assert "Beacon-Linux-0.7.0.tar.gz" in linux
    assert '@app.get("/api/messages/search")' in main
    assert 'name: beacon-data' in (ROOT / "compose.dokploy.yaml").read_text()
