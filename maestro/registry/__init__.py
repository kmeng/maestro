"""User-global recent-projects registry — ``~/.maestro/projects.json``.

Read/write semantics per design 14 § Project registry. The registry is
a cache — corruption or version mismatch is treated as absent and
rebuilt on next write rather than surfaced to the user.

Public API:

- :class:`ProjectEntry` — one entry returned by :func:`read_registry`.
- :func:`read_registry` — newest-first list of entries; silently drops
  dead paths.
- :func:`upsert_project` — atomically write-or-update one entry.
- :data:`CURRENT_SCHEMA_VERSION` — schema version stamped into the file.
"""
from __future__ import annotations

from .projects import (
    CURRENT_SCHEMA_VERSION,
    ProjectEntry,
    read_registry,
    upsert_project,
)

__all__ = [
    "ProjectEntry",
    "read_registry",
    "upsert_project",
    "CURRENT_SCHEMA_VERSION",
]
