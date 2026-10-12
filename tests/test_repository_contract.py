"""Keep distributable, docs and server versions aligned."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_documentation_and_platform_sources_exist():
    for relative in (
        "README.md", "CHANGELOG.md", "docs/INSTALL.md", "docs/DOKPLOY.md",
        "docs/API.md", "docs/ARCHITECTURE.md", "docs/SECURITY.md",
        "docs/TROUBLESHOOTING.md", "docs/DEVELOPMENT.md",
        "docs/RELEASE-CHECKLIST.md",
        "docs/GITHUB-ACTIONS-RUNNER-RECOVERY.md", "clients/desktop/README.md",
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
        "clients/desktop-go/internal/beacon/sync.go",
        "clients/desktop-go/internal/beacon/sync_test.go",
        "docs/MULTI-DEVICE-DELIVERY.md",
    ):
        assert (ROOT / relative).is_file(), relative


def test_versions_and_server_registration():
    main = (ROOT / "server/main.py").read_text()
    android = (ROOT / "clients/android/app/build.gradle").read_text()
    workflow = (ROOT / ".github/workflows/windows.yml").read_text()
    linux = (ROOT / ".github/workflows/linux.yml").read_text()
    assert 'version="0.8.0"' in main
    assert "versionName '0.8.0'" in android
    assert "versionCode 8" in android
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


def test_connection_lifecycle_and_batched_presence_are_wired():
    server = (ROOT / "server/main.py").read_text()
    aim = (ROOT / "server/aim.py").read_text()
    desktop = (ROOT / "clients/desktop-go/cmd/beacon/main.go").read_text()
    assert "@contextmanager\ndef connection():" in server
    assert "db.rollback()" in server and "db.close()" in server
    assert "idx_sessions_presence" in server
    assert "def attach_presence(db, rows):" in aim
    assert "range(0, len(user_ids), 400)" in aim
    assert "reflect.DeepEqual" in desktop
    assert "errors.Is(err,beacon.ErrUnauthorized)" in desktop


def test_all_four_real_build_workflows_support_runner_recovery():
    """Self-hosted mode must run the exact same tests, binaries and artifacts."""
    for filename in ("ci.yml", "windows.yml", "linux.yml", "android.yml"):
        text = (ROOT / ".github/workflows" / filename).read_text(encoding="utf-8")
        assert "workflow_dispatch:" in text, filename
        assert "BEACON_USE_SELF_HOSTED_RUNNERS" in text, filename
        assert "github-hosted" in text and "self-hosted" in text
        assert "fromJSON(" in text, filename
        assert "github.event_name != 'pull_request'" in text, filename
        assert "permissions:" in text and "contents: read" in text
        label = "beacon-windows" if filename == "windows.yml" else "beacon-linux"
        assert label in text, filename
    windows = (ROOT / ".github/workflows/windows.yml").read_text()
    linux = (ROOT / ".github/workflows/linux.yml").read_text()
    android = (ROOT / ".github/workflows/android.yml").read_text()
    ci = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "build-desktop-windows.ps1" in windows
    assert "Get-FileHash" in windows
    assert "actions/upload-artifact@" in windows
    assert "retention-days: 7" in windows
    assert "build-desktop-linux.sh" in linux
    assert "sha256sum -c" in linux
    assert "actions/upload-artifact@" in linux
    assert "retention-days: 7" in linux
    assert ":app:assembleDebug" in android
    assert "actions/upload-artifact@" in android
    assert "retention-days: 7" in android
    assert "pytest -q" in ci and "docker build" in ci
    assert (ROOT / "docs/SELF-HOSTED-BUILD-RUNNERS.md").is_file()


def test_multi_device_event_cursor_and_display_read_contract():
    """Prevent regressions to unread-count-only notifications and premature read state."""
    sync = (ROOT / "clients/desktop-go/internal/beacon/sync.go").read_text()
    main = (ROOT / "clients/desktop-go/cmd/beacon/main.go").read_text()
    chat = (ROOT / "clients/desktop-go/cmd/beacon/chat.go").read_text()
    android = (ROOT / "clients/android/app/src/main/java/net/gigabytegrove/beacon/MainActivity.java").read_text()
    for api in ("LatestEventID(", "EventBatch(", "CatchUp("):
        assert api in sync
    assert "cursor=next" in main
    assert "notifyNewMessages(arrivals)" in main
    assert "ch.lastRead=id" in chat
    assert "MarkRead(requestCtx,ch.peer.ID,id)" in chat
    assert "markRenderedConversationRead(snap.peer, snap.messages);" in android
    assert "displayedReadCursors" in android


def test_go_native_primary_client_integrates_premium_brand():
    folder = ROOT / "clients/desktop-go/cmd/beacon"
    main = (folder / "main.go").read_text()
    chat = (folder / "chat.go").read_text()
    brand = (folder / "brand.go").read_text()
    assert "Settings().SetTheme(beaconTheme{" in main
    assert "beaconHeader(" in main
    assert "Search your buddies" in main
    assert "No buddies to show" in main
    assert "layout.NewSpacer()" in chat
    assert "type beaconTheme struct" in brand
