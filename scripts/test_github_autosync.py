#!/usr/bin/env python3
"""Offline tests for auto-sync stale-regression and git-relation rules."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("github_autosync", ROOT / "github_autosync.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_stale_regression_blocks_qubic_over_sbsports():
    local = b'login https://betbck.com/Qubic/SecurityPage.php\n'
    remote = b'https://betbck.com/cloud/api/System/authenticateCustomer\nsbsports.html\nGet_LeagueLines2\n'
    assert mod.is_stale_regression("backend/config.json", local, remote)


def test_cloud_local_may_overwrite_stale_remote():
    local = b'authenticateCustomer\nsbsports.html\nGet_LeagueLines2\n'
    remote = b'https://betbck.com/Qubic/StraightSportSelection.php\n'
    assert not mod.is_stale_regression("backend/config.json", local, remote)


def test_identical_cloud_is_not_regression():
    body = b'authenticateCustomer\nsbsports.html\n'
    assert not mod.is_stale_regression("backend/config.json", body, body)


def test_helper_version_guard():
    old = b'{"version": "0.1.0"}'
    new = b'{"version": "0.2.0"}'
    assert mod.is_stale_regression("betbck_extension/manifest.json", old, new)
    assert not mod.is_stale_regression("betbck_extension/manifest.json", new, old)


def test_relation_equal_and_missing_remote_commit():
    assert mod.relation_to_remote("abc", "abc") == "equal"
    # remote sha this clone does not have → behind (do not upload)
    assert mod.relation_to_remote("abc", "def123nonexistent") == "behind"


def test_blob_sha_stable():
    assert mod.git_blob_sha(b"hello") == mod.git_blob_sha(b"hello")
    assert mod.git_blob_sha(b"hello") != mod.git_blob_sha(b"world")


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"ALL {len(tests)} TESTS PASSED")
