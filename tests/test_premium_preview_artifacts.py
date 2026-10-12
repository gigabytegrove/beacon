"""Preview artifacts are authentic, checksum-verified, and never replace the main clients.

These tests validate the locally built *experimental* Win32/X11 preview files.
They intentionally do not claim Fyne or Android APK builds passed.
"""
from pathlib import Path
import hashlib
import tarfile
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "releases/previews/2026-10-11"
WIN = RELEASE / "Beacon-Messenger-Windows-x64-Premium-20261011.zip"
LINUX = RELEASE / "Beacon-Messenger-Linux-x64-Premium-20261011.tar.gz"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def test_windows_archive_contains_genuine_pe_executable():
    assert digest(WIN) == "b70f1221742286bea9e4ab809a527fc3a5c768d7b68ce035845b09586b00ccf9"
    with zipfile.ZipFile(WIN) as archive:
        assert archive.testzip() is None
        matches = [name for name in archive.namelist() if name.endswith(".exe")]
        assert len(matches) == 1
        binary = archive.read(matches[0])
    assert len(binary) > 1_000_000
    assert hashlib.sha256(binary).hexdigest() == "adabec63b02a4eb4b517f1828669ec806e9ee292203c628794ebfebad0690322"
    assert binary.startswith(b"MZ")
    pe_offset = int.from_bytes(binary[0x3C:0x40], "little")
    assert binary[pe_offset:pe_offset + 4] == b"PE\x00\x00"


def test_linux_archive_contains_genuine_elf_executable():
    assert digest(LINUX) == "3f6d79308fffa60301a4196e7ca8470c400b07006f9179d567049607803ba497"
    with tarfile.open(LINUX, "r:gz") as archive:
        binary_entries = [
            item for item in archive.getmembers()
            if item.isfile() and item.name.endswith("/Beacon-Messenger-Linux-x64")
        ]
        assert len(binary_entries) == 1
        data = archive.extractfile(binary_entries[0]).read(64)
    assert data[:4] == b"\x7fELF"
    assert data[4] == 2  # ELF64


def test_preview_is_isolated_from_main_go_fyne_client():
    assert (ROOT / "clients/desktop-native-preview/go.mod").exists()
    assert (ROOT / "clients/desktop-go/go.mod").exists()
    primary = (ROOT / "clients/desktop-go/go.mod").read_text()
    assert "fyne.io/fyne/v2" in primary
    assert (ROOT / "clients/android/app/src/main/java/net/gigabytegrove/beacon/MainActivity.java").exists()


def test_android_premium_kit_is_layout_resources_not_a_fake_apk():
    kit = ROOT / "design/android-premium/app/src/main/res"
    xml_files = list(kit.rglob("*.xml"))
    assert len(xml_files) >= 10
    for path in xml_files:
        ET.parse(path)
    assert (kit / "layout/beacon_login.xml").exists()
    assert (kit / "layout/beacon_chat.xml").exists()


def test_marketing_previews_and_documentation_exist():
    assert (ROOT / "docs/images/beacon-premium/overview.png").exists()
    assert (ROOT / "docs/PREMIUM-PREVIEW.md").exists()
    assert (ROOT / "clients/desktop-native-preview/BUILDING.md").exists()
    assert (RELEASE / "SHA256SUMS.txt").exists()
