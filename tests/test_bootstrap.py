"""No HTTP endpoint may generate or leak a first-run admin setup code."""
from server.bootstrap import code_path, matches_setup_code, obtain_setup_code, retire_setup_code


def test_setup_code_is_persistent_secret_and_is_single_use(tmp_path):
    db = str(tmp_path / "beacon.db")
    token = obtain_setup_code(db)
    assert len(token) >= 32
    assert token == obtain_setup_code(db)
    assert code_path(db).stat().st_mode & 0o777 == 0o600
    assert matches_setup_code(db, token)
    assert not matches_setup_code(db, "wrong-setup-code")
    assert not matches_setup_code(db, "")
    retire_setup_code(db)
    assert not code_path(db).exists()
    assert not matches_setup_code(db, token)
    assert obtain_setup_code(db) != token


def test_code_file_symlinks_and_corrupted_codes_are_rejected(tmp_path):
    db = str(tmp_path / "beacon.db")
    path = code_path(db)
    path.write_text("short")
    try:
        obtain_setup_code(db)
    except RuntimeError:
        pass
    else:
        raise AssertionError("A corrupted code must not be used")
    path.unlink()
    other = tmp_path / "other-file"
    other.write_text("x" * 43)
    path.symlink_to(other)
    assert not matches_setup_code(db, "x" * 43)
    try:
        obtain_setup_code(db)
    except RuntimeError:
        pass
    else:
        raise AssertionError("A symlink must not be accepted as a code file")
