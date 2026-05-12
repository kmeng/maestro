from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Union


class Operation(str, Enum):
    CREATE = "CREATE"
    APPEND_DELIMITED = "APPEND_DELIMITED"
    NOOP = "NOOP"
    CONFLICT = "CONFLICT"


class ConflictReason(str, Enum):
    REPLACEMENT_DIFFERS = "replacement_differs"
    DELIMITER_BODY_DIFFERS = "delimiter_body_differs"
    DELIMITER_VERSION_MISMATCH = "delimiter_version_mismatch"
    MULTIPLE_DELIMITER_BLOCKS = "multiple_delimiter_blocks"
    UNCLOSED_DELIMITER = "unclosed_delimiter"


@dataclass(frozen=True)
class PreflightCheck:
    """One pre-flight check result (T2.3).

    The UI (T2.7) renders these as a banner above the per-file plan
    rows — passing checks shown as ✓ summary; failing checks shown
    prominently and disable the Apply button.

    Names are stable identifiers (``directory_exists`` / ``git_state`` /
    ``clean_tree`` / ``no_existing_maestro``) so the UI can target
    specific rows for layout decisions. Messages are user-facing
    Chinese strings.
    """
    name: str
    passed: bool
    message: str


@dataclass(frozen=True)
class ReplacementFile:
    """A file Maestro fully owns. Idempotence by exact-bytes match.

    Used for `.maestro/.gitignore`, `.gitignore`, `README.md` — files where
    Maestro writes the whole content and the user is not expected to
    co-author. Any byte-level divergence from Maestro's rendered content
    surfaces as a `CONFLICT` (we never silently overwrite user edits).
    """
    path: str          # relative to project root, e.g. ".maestro/.gitignore"
    rendered: bytes    # full file content to write on CREATE


@dataclass(frozen=True)
class MergeableFile:
    """A file Maestro shares with the user (currently only CLAUDE.md).

    Idempotence by delimiter scan: Maestro owns the bytes BETWEEN
    `<!-- maestro:start v=N -->` and `<!-- maestro:end v=N -->`; the rest
    of the file is the user's. The scaffolding engine looks for an
    existing Maestro section by delimiter and reasons about it
    accordingly.
    """
    path: str
    section_body: bytes      # text BETWEEN the start/end markers (no markers themselves)
    standalone_full: bytes   # full file content when target absent (markers included)
    section_version: int = 1


FileSpec = Union[ReplacementFile, MergeableFile]


@dataclass(frozen=True)
class PlanRow:
    """One file's outcome in a scaffolding plan. The UI renders one row
    per PlanRow; `detail` is the human-readable summary shown to the user."""
    path: str
    op: Operation
    detail: str
    conflict_reason: ConflictReason | None = None  # only set when op == CONFLICT


@dataclass(frozen=True)
class Plan:
    """A scaffolding plan — what would happen to each file in the input
    FileSpec list, in input order. Pure data; the apply executor (T2.2)
    walks the rows and performs the actual writes.

    ``preflight`` carries pre-flight check results (T2.3). Default
    empty tuple keeps all T2.1-era constructions unchanged:
    ``Plan(rows=(...))`` is still valid.
    """
    rows: tuple[PlanRow, ...]
    preflight: tuple[PreflightCheck, ...] = ()
