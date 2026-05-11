"""Project registry — read/write ``~/.maestro/projects.json``.

Schema per design 14 § Project registry::

    {
      "schema_version": 1,
      "projects": [
        {"path": "/abs/path", "last_opened_at": "2026-05-08T14:23:11Z"}
      ]
    }

This is a *cache*, not authoritative state — every read-path failure
(missing file, bad JSON, wrong schema_version, malformed entries, dead
paths) is handled silently and treated as "absent." `upsert_project`
always succeeds: if the on-disk file is corrupt it gets rebuilt with
the new entry as the sole content.
"""
from __future__ import annotations

import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from maestro.paths import projects_registry_path

CURRENT_SCHEMA_VERSION = 1


def _format_utc_timestamp(dt: datetime) -> str:
    """Render a datetime as ISO-8601 UTC with the ``Z`` suffix."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_timestamp(s: str) -> datetime | None:
    """Parse an ISO-8601 timestamp accepting both ``Z`` and ``+00:00`` suffixes.

    Returns a tz-aware UTC datetime, or ``None`` if unparseable.
    """
    try:
        # fromisoformat doesn't accept "Z" before Python 3.11. Normalize.
        normalised = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalised)
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt


@dataclass(frozen=True)
class ProjectEntry:
    path: Path
    last_opened_at: datetime  # tz-aware UTC


def read_registry() -> list[ProjectEntry]:
    """Read ``~/.maestro/projects.json`` and return entries newest-first.

    Returns the empty list on any of: file missing, JSON parse failure,
    top-level shape wrong, ``schema_version`` missing or unrecognized,
    or ``projects`` not a list. Silently drops entries whose ``path``
    no longer exists on disk, whose shape is malformed, or whose
    timestamp doesn't parse.

    All errors are intentionally silent — this is cache, not state.
    Pruning is in-memory only; the on-disk file isn't rewritten by a
    read (that's the lazy-write-back rule from design D4).
    """
    reg_path = projects_registry_path()
    if not reg_path.is_file():
        return []

    try:
        with reg_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        # Corrupt or unreadable — cache rebuild happens on next write.
        return []

    if not isinstance(data, dict):
        return []
    if data.get("schema_version") != CURRENT_SCHEMA_VERSION:
        return []
    projects_list = data.get("projects")
    if not isinstance(projects_list, list):
        return []

    entries: list[ProjectEntry] = []
    for item in projects_list:
        if not isinstance(item, dict):
            continue
        path_str = item.get("path")
        timestamp_str = item.get("last_opened_at")
        if not isinstance(path_str, str) or not isinstance(timestamp_str, str):
            continue
        ts = _parse_timestamp(timestamp_str)
        if ts is None:
            continue
        p = Path(path_str)
        if not p.exists():
            # Dead-path pruning — silently drop entries the user has since
            # deleted/moved. Lazy write-back: the file is not rewritten
            # here; whatever next upsert happens will persist the pruned form.
            continue
        entries.append(ProjectEntry(path=p, last_opened_at=ts))

    entries.sort(key=lambda e: e.last_opened_at, reverse=True)
    return entries


def upsert_project(path: Path, *, now: datetime | None = None) -> None:
    """Add or update the entry for ``path``, setting ``last_opened_at = now``.

    Atomic via write-temp-then-os.replace. Creates the parent directory
    if missing. If the existing registry is corrupt or has wrong
    schema_version, starts fresh — upsert always succeeds with at least
    the new entry as the sole content.

    The path is normalized via ``.resolve()`` before storing; duplicate-
    detection compares resolved paths.

    ``now`` defaults to ``datetime.now(timezone.utc)``; the parameter
    exists for test determinism.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    resolved = path.resolve()
    reg_path = projects_registry_path()
    reg_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing — but tolerate every form of corruption by falling
    # back to a fresh empty registry. The user never sees a "registry
    # broken" error; cache rebuilds itself.
    try:
        with reg_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        data = None

    if (
        not isinstance(data, dict)
        or data.get("schema_version") != CURRENT_SCHEMA_VERSION
        or not isinstance(data.get("projects"), list)
    ):
        projects: list = []
    else:
        projects = data["projects"]

    new_entry = {
        "path": str(resolved),
        "last_opened_at": _format_utc_timestamp(now),
    }

    # Upsert by resolved path equality. Malformed pre-existing entries
    # are dropped at this point (they'd have been dropped by read_registry
    # anyway; this write is when we actually persist that decision).
    new_projects: list[dict] = []
    updated = False
    for proj in projects:
        if not isinstance(proj, dict):
            continue
        proj_path_str = proj.get("path")
        if not isinstance(proj_path_str, str):
            continue
        try:
            proj_path = Path(proj_path_str)
        except Exception:
            continue
        if proj_path == resolved:
            new_projects.append(new_entry)
            updated = True
        else:
            new_projects.append(proj)

    if not updated:
        new_projects.append(new_entry)

    new_data = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "projects": new_projects,
    }

    # Atomic write: temp file in the same directory + os.replace. The
    # random suffix is to avoid collisions if two processes race; the
    # `tmp_path.unlink(missing_ok=True)` cleanup runs even if the write
    # itself raised partway.
    tmp_suffix = secrets.token_hex(8)
    tmp_path = reg_path.parent / f"projects.json.tmp.{tmp_suffix}"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(new_data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, reg_path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise
