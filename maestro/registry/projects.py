"""Project registry — read/write ``~/.maestro/projects.json``.

Schema per design 14 § Project registry::

    {
      "schema_version": 1,
      "projects": [
        {"path": "/abs/path", "last_opened_at": "2026-05-08T14:23:11Z"}
      ]
    }

Failure contract — read_registry()
    This function NEVER raises.
    Returns ``list[ProjectEntry]`` (possibly empty).

    Returns empty list on:
        - File missing
        - JSON parse failure
        - Top-level not a dict
        - ``schema_version`` missing or != ``CURRENT_SCHEMA_VERSION``
        - ``'projects'`` key missing or not a list

    Returns the surviving entries (possibly empty) on:
        - Per-entry shape malformed (not dict / missing keys / wrong types)
        - ``_parse_timestamp`` returns ``None``
        - ``Path(path_str)`` raises ``ValueError``, ``OverflowError``, or any other
          ``Exception`` (caught by per-entry blanket handler)
        - ``Path.exists()`` raises (rare; e.g., permission denied on parent)
        - Path resolves to non-existent target (dead-path pruning)

Failure contract — upsert_project()
    This function NEVER raises.
    All failure paths are swallowed silently:

        - Disk full / permission denied / OS errors during ``mkdir(...)``,
          ``open(tmp_path, "w")``, ``json.dump(...)``, or ``os.replace(...)``
          → swallowed (caller is not informed)
        - ``path.resolve()`` failure (broken symlinks / permission issues)
          → swallowed (cache write aborted silently)
        - Corrupt existing registry → registry is rebuilt from scratch with
          just the new entry as sole content
        - Tmp file cleanup on any partial-write → guaranteed via inner
          ``try/except`` that runs ``tmp_path.unlink(missing_ok=True)``
          on any error path

    Rationale: this is a cache write. Caller has no recourse if it fails
    (retrying won't help; surfacing to user is noise). Best-effort semantic
    is appropriate.
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
    """See module docstring for the full failure contract."""
    reg_path = projects_registry_path()
    if not reg_path.is_file():
        return []
    try:
        with reg_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
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
        try:
            if not isinstance(item, dict):
                continue
            path_str = item.get("path")
            timestamp_str = item.get("last_opened_at")
            if not isinstance(path_str, str) or not isinstance(timestamp_str, str):
                continue
            ts = _parse_timestamp(timestamp_str)
            if ts is None:
                continue
            # Path() can raise ValueError on NUL bytes; .exists() can raise
            # OSError on rare permission edge cases. The blanket Exception
            # catch is intentional: this is cache code, not authoritative —
            # any failure to interpret an entry means we drop it silently.
            p = Path(path_str)
            if not p.exists():
                # Dead-path pruning — silently drop entries the user has since
                # deleted/moved. Lazy write-back: the file is not rewritten
                # here; whatever next upsert happens will persist the pruned form.
                continue
            entries.append(ProjectEntry(path=p, last_opened_at=ts))
        except Exception:
            # Any unexpected failure interpreting this entry → drop it.
            # See module docstring: read_registry NEVER raises.
            continue
    entries.sort(key=lambda e: e.last_opened_at, reverse=True)
    return entries


def upsert_project(path: Path, *, now: datetime | None = None) -> None:
    """See module docstring for the full failure contract."""
    if now is None:
        now = datetime.now(timezone.utc)

    try:
        resolved = path.resolve()
    except Exception:
        # path.resolve() can raise OSError on broken symlinks or
        # permission issues. Cache write — silently abort.
        return

    try:
        reg_path = projects_registry_path()
        reg_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing — tolerate every form of corruption by falling back
        # to a fresh empty registry. The user never sees a "registry broken"
        # error; cache rebuilds itself.
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

        # Atomic write — temp file in same directory + os.replace. Random
        # suffix avoids collisions if two processes race; the inner
        # try/except guarantees tmp cleanup on the partial-write path.
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
            # Re-raise locally so the outer except catches it. This couples
            # tmp cleanup tightly to the write block while still letting
            # the outer block swallow everything for the caller.
            raise
    except Exception:
        # Any filesystem error — cache write best-effort, swallow.
        # See module docstring: upsert_project NEVER raises.
        return
