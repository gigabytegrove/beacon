"""Structural checks that also run when no Android SDK is available on the CI runner."""
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "clients" / "android"
JAVA = BASE / "app/src/main/java/net/gigabytegrove/beacon"


def test_remote_messaging_service_wiring():
    manifest = (BASE / "app/src/main/AndroidManifest.xml").read_text()
    assert 'android:foregroundServiceType="remoteMessaging"' in manifest
    assert 'android.permission.FOREGROUND_SERVICE_REMOTE_MESSAGING' in manifest
    assert 'android:exported="false"' in manifest
    activity = (JAVA / "MainActivity.java").read_text()
    service = (JAVA / "BeaconMonitorService.java").read_text()
    assert "stopMonitor()" in activity
    assert "startMonitor()" in activity
    assert "ACTION_START" in service and "ACTION_STOP" in service
    assert '"/api/events?after="' in service
    assert '"/api/presence"' in service
    assert "new SecureSession(this).load()" in service
    assert "prefs.edit().putLong(cursorKey, cursor)" in service
    assert "FOREGROUND_SERVICE_TYPE_REMOTE_MESSAGING" in service


def test_version_and_android_token_security():
    script = (BASE / "app/build.gradle").read_text()
    assert "versionCode 7" in script
    assert "0.7.0" in script
    session = (JAVA / "SecureSession.java").read_text()
    assert "AndroidKeyStore" in session
    assert "AES/GCM/NoPadding" in session

def test_native_android_account_and_search_interfaces():
    activity = (JAVA / "MainActivity.java").read_text()
    for fragment in ("editProfile()", "manageDevices()", "searchMessages(int peer)",
                     "chooseAvatar()", "onActivityResult(", "AtomicBoolean",
                     "openIncomingConversation(", "public static volatile boolean isUiVisible"):
        assert fragment in activity
    service = (JAVA / "BeaconMonitorService.java").read_text()
    assert "MainActivity.isUiVisible" in service
    assert "beacon_peer_id" in service

def test_android_read_receipts_follow_visible_render():
    """Read receipts must not clear unread counts before messages are displayed."""
    activity = (JAVA / "MainActivity.java").read_text()
    method_start = activity.index("private void poll()")
    method_end = activity.index("private static final class Snapshot", method_start)
    network_poll = activity[method_start:method_end]
    assert 'request("/conversations/" + peer + "/read"' not in network_poll
    assert "renderChat(snap);" in network_poll
    assert "markRenderedConversationRead(snap.peer, snap.messages);" in network_poll
    method = activity[activity.index("private void markRenderedConversationRead("):]
    assert "displayedReadCursors" in method
    assert "if (messages == null || messagesList == null || !foreground) return;" in method
    assert 'request("/conversations/" + peer + "/read"' in method
