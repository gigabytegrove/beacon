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
        "compose.dokploy.yaml", "server/bootstrap.py",
        "tests/test_setup.py",
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
    server = (ROOT / "server/main.py").read_text()
    android = (ROOT / "clients/android/app/build.gradle").read_text()
    assert 'os.getenv("BEACON_RUNTIME_VERSION", os.getenv("BEACON_VERSION", "0.9.1"))' in server
    assert "versionName '0.8.0'" in android
    assert "versionCode 8" in android
    assert '@app.get("/api/messages/search")' in server
    assert '@app.get("/api/setup/status")' in server
    assert '@app.post("/api/setup", status_code=201)' in server
    compose = (ROOT / "compose.dokploy.yaml").read_text()
    assert 'name: beacon-data' in compose
    assert 'beacon-data:/data' in compose
    assert 'build:' in compose and 'github.com/gigabytegrove/beacon.git#main' in compose


def test_primary_go_desktop_and_manual_builds_not_github_actions():
    desktop_module = (ROOT / "clients/desktop-go/go.mod").read_text()
    assert "fyne.io/fyne/v2" in desktop_module
    assert "github.com/zalando/go-keyring" in desktop_module
    readme = (ROOT / "README.md").read_text()
    assert "do **not** need Python" in readme
    required = (
        "scripts/build-desktop-windows.ps1",
        "scripts/build-desktop-linux.sh",
        "scripts/build-android-windows.ps1",
        "docs/BUILD-AND-TEST.md",
        "tools/beacon-probe/main.go",
        "tools/beacon-probe/README.md",
    )
    for relative in required:
        assert (ROOT / relative).is_file(), relative
    assert "It is NOT the Beacon graphical instant messaging client." in (
        ROOT / "tools/beacon-probe/main.go").read_text()


def test_all_github_actions_workflows_remain_disabled():
    workflows = ROOT / ".github/workflows"
    if workflows.exists():
        assert not list(workflows.glob("*.yml"))
        assert not list(workflows.glob("*.yaml"))


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
    assert "container.NewGridWrap(" in brand
    assert "dot.SetMinSize(" not in brand
