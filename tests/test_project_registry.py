"""Unit tests for the project registry (T2.5)."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from maestro.registry.projects import (
    read_registry,
    upsert_project,
    _format_utc_timestamp,
)


@pytest.fixture
def registry_path(tmp_path, monkeypatch):
    """Redirect the registry file path to a temporary location.

    Patches the imported reference inside maestro.registry.projects (the
    "import-by-name monkeypatch" trap from docs/playbook/common-traps.md).
    """
    p = tmp_path / "projects.json"
    monkeypatch.setattr(
        "maestro.registry.projects.projects_registry_path", lambda: p
    )
    return p


# -- read_registry -----------------------------------------------------------

def test_read_returns_empty_when_file_absent(registry_path):
    assert read_registry() == []


def test_read_returns_empty_when_parse_fails(registry_path):
    registry_path.write_text("this is not json")
    assert read_registry() == []


def test_read_returns_empty_when_schema_version_unrecognized(registry_path):
    registry_path.write_text(json.dumps({"schema_version": 99, "projects": []}))
    assert read_registry() == []


def test_read_returns_empty_when_schema_version_missing(registry_path):
    registry_path.write_text(json.dumps({"projects": []}))
    assert read_registry() == []


def test_read_returns_empty_when_projects_key_missing(registry_path):
    registry_path.write_text(json.dumps({"schema_version": 1}))
    assert read_registry() == []


def test_read_drops_dead_paths(registry_path, tmp_path):
    existing_dir = tmp_path / "real_dir"
    existing_dir.mkdir()
    data = {
        "schema_version": 1,
        "projects": [
            {"path": str(existing_dir), "last_opened_at": "2026-05-08T14:23:11Z"},
            {"path": "/nonexistent/path/xyz", "last_opened_at": "2026-05-08T14:23:12Z"},
        ],
    }
    registry_path.write_text(json.dumps(data))
    result = read_registry()
    assert len(result) == 1
    assert result[0].path == existing_dir


def test_read_drops_malformed_entries(registry_path, tmp_path):
    good_dir = tmp_path / "good"
    good_dir.mkdir()
    data = {
        "schema_version": 1,
        "projects": [
            {"path": str(good_dir), "last_opened_at": "2026-05-08T14:23:11Z"},
            {"last_opened_at": "2026-05-08T14:23:11Z"},      # missing path
            {"path": str(good_dir), "last_opened_at": "not-a-date"},  # bad ts
        ],
    }
    registry_path.write_text(json.dumps(data))
    result = read_registry()
    assert len(result) == 1
    assert result[0].path == good_dir


def test_read_sorts_newest_first(registry_path, tmp_path):
    dirs = []
    for name in ("d1", "d2", "d3"):
        d = tmp_path / name
        d.mkdir()
        dirs.append(d)
    d1, d2, d3 = dirs
    t1 = datetime(2026, 5, 8, 10, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 5, 9, 10, 0, 0, tzinfo=timezone.utc)  # newest
    t3 = datetime(2026, 5, 7, 10, 0, 0, tzinfo=timezone.utc)  # oldest
    registry_path.write_text(json.dumps({
        "schema_version": 1,
        "projects": [
            {"path": str(d1), "last_opened_at": _format_utc_timestamp(t1)},
            {"path": str(d2), "last_opened_at": _format_utc_timestamp(t2)},
            {"path": str(d3), "last_opened_at": _format_utc_timestamp(t3)},
        ],
    }))
    result = read_registry()
    assert [e.path for e in result] == [d2, d1, d3]


# -- upsert_project ----------------------------------------------------------

def test_upsert_creates_file_when_absent(registry_path, tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    upsert_project(target, now=datetime(2026, 5, 8, 14, 23, 11, tzinfo=timezone.utc))
    content = json.loads(registry_path.read_text())
    assert content["schema_version"] == 1
    assert len(content["projects"]) == 1
    assert content["projects"][0]["path"] == str(target.resolve())
    assert content["projects"][0]["last_opened_at"] == "2026-05-08T14:23:11Z"


def test_upsert_creates_parent_dir_when_absent(tmp_path, monkeypatch):
    nested = tmp_path / "nonexistent" / "sub" / "projects.json"
    monkeypatch.setattr(
        "maestro.registry.projects.projects_registry_path", lambda: nested
    )
    target = tmp_path / "foo"
    target.mkdir()
    upsert_project(target)
    assert nested.is_file()


def test_upsert_updates_existing_entry(registry_path, tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    t1 = datetime(2026, 5, 8, 14, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 5, 9, 10, 0, 0, tzinfo=timezone.utc)
    upsert_project(target, now=t1)
    upsert_project(target, now=t2)
    content = json.loads(registry_path.read_text())
    assert len(content["projects"]) == 1
    assert content["projects"][0]["last_opened_at"] == _format_utc_timestamp(t2)


def test_upsert_adds_second_entry_for_different_path(registry_path, tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    upsert_project(a)
    upsert_project(b)
    content = json.loads(registry_path.read_text())
    paths = {proj["path"] for proj in content["projects"]}
    assert paths == {str(a.resolve()), str(b.resolve())}


def test_upsert_resolves_path(registry_path, tmp_path):
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    symlink = tmp_path / "link"
    symlink.symlink_to(real_dir, target_is_directory=True)
    upsert_project(symlink)
    content = json.loads(registry_path.read_text())
    assert content["projects"][0]["path"] == str(real_dir.resolve())


def test_upsert_atomic_write_no_torn_file(registry_path, tmp_path):
    target = tmp_path / "x"
    target.mkdir()
    upsert_project(target)
    parent = registry_path.parent
    leftover_tmps = [
        child for child in parent.iterdir()
        if child.name.startswith("projects.json.tmp.")
    ]
    assert leftover_tmps == []


def test_upsert_recovers_when_existing_file_corrupt(registry_path, tmp_path):
    registry_path.write_text("garbage")
    target = tmp_path / "recovery"
    target.mkdir()
    upsert_project(target)
    content = json.loads(registry_path.read_text())
    assert content["schema_version"] == 1
    assert len(content["projects"]) == 1
    assert content["projects"][0]["path"] == str(target.resolve())


def test_upsert_accepts_both_z_and_offset_timestamps_on_subsequent_reads(
    registry_path, tmp_path
):
    existing = tmp_path / "existing"
    new_one = tmp_path / "new_one"
    existing.mkdir()
    new_one.mkdir()
    # Write a file using +00:00 form directly
    registry_path.write_text(json.dumps({
        "schema_version": 1,
        "projects": [
            {"path": str(existing), "last_opened_at": "2026-05-08T14:23:11+00:00"}
        ],
    }))
    # Upsert preserves the +00:00 entry and adds the Z-formatted new one
    upsert_project(
        new_one, now=datetime(2026, 5, 9, 10, 0, 0, tzinfo=timezone.utc)
    )
    result = read_registry()
    assert len(result) == 2
    assert {e.path for e in result} == {existing.resolve(), new_one.resolve()}


# -- Silent-failure contract (post-review fix for #37) ----------------------

def test_read_registry_silent_on_nul_byte_path(registry_path, tmp_path):
    """A registry entry whose path contains NUL bytes must be silently
    dropped — Path(<NUL>) raises ValueError. Per the failure contract,
    read_registry NEVER raises.
    """
    good_dir = tmp_path / "good"
    good_dir.mkdir()
    data = {
        "schema_version": 1,
        "projects": [
            {"path": str(good_dir), "last_opened_at": "2026-05-08T14:23:11Z"},
            # NUL byte forces Path() to raise ValueError
            {"path": "bad\x00path", "last_opened_at": "2026-05-08T14:23:12Z"},
        ],
    }
    registry_path.write_text(json.dumps(data))
    # Must not raise; bad entry is silently dropped.
    result = read_registry()
    assert len(result) == 1
    assert result[0].path == good_dir


def test_read_registry_silent_on_is_file_permission_error(registry_path, tmp_path, monkeypatch):
    """If Path.is_file() raises (e.g., PermissionError on inaccessible
    parent), read_registry must still return [] rather than propagate.
    Per the failure contract, read_registry NEVER raises — and the
    bulletproof outer try/except enforces this structurally.
    """
    # Make registry_path.is_file() raise. monkeypatch.setattr on the
    # instance is awkward for Path; instead, swap the path-getter for
    # a custom Path subclass whose is_file() raises.
    class HostilePath(type(registry_path)):
        def is_file(self):
            raise PermissionError("simulated permission denied on parent")

    hostile = HostilePath(str(registry_path))
    monkeypatch.setattr(
        "maestro.registry.projects.projects_registry_path", lambda: hostile
    )
    # Must NOT raise. Empty list since we couldn't even probe the file.
    assert read_registry() == []


def test_upsert_project_silent_on_filesystem_error(registry_path, tmp_path, monkeypatch):
    """A filesystem error during the write path must NOT propagate.
    Per the failure contract, upsert_project NEVER raises.
    """
    target = tmp_path / "target"
    target.mkdir()

    # Force os.replace to raise — simulates disk full / permission denied
    # at the atomic-rename step.
    import maestro.registry.projects as pmod
    def boom(*a, **kw):
        raise OSError("simulated disk full")
    monkeypatch.setattr(pmod.os, "replace", boom)

    # Must NOT raise — caller has no recourse for cache-write failure.
    upsert_project(target)

    # No torn tmp file should remain (cleanup must run on the error path).
    parent = registry_path.parent
    if parent.exists():
        leftovers = [c for c in parent.iterdir() if c.name.startswith("projects.json.tmp.")]
        assert leftovers == [], f"Found orphan tmp files: {leftovers}"
