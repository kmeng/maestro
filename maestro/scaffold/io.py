"""Filesystem I/O layer for the scaffolding engine (T2.2).

Provides atomic write-then-rename, CRLF-tolerant reads, and a generator
``apply_plan`` that walks a :class:`~maestro.scaffold.Plan` row by row
and emits per-file events.

Per ADR-0006 § Atomicity: writes are per-file atomic via ``os.replace``;
the engine does not transactionally roll back across multiple files. A
partial-apply leaves the partial state on disk, which is safe to recover
from via an idempotent re-run.
"""
from __future__ import annotations

import os
import secrets
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Union

from .operations import (
    FileSpec,
    MergeableFile,
    Operation,
    Plan,
    ReplacementFile,
)


@dataclass(frozen=True)
class FileStarted:
    """Emitted before any I/O for a row begins."""
    path: str


@dataclass(frozen=True)
class FileSucceeded:
    """Emitted after a row completes successfully (write done, or NOOP)."""
    path: str
    op: Operation  # CREATE / APPEND_DELIMITED / NOOP


@dataclass(frozen=True)
class FileFailed:
    """Emitted when a row's I/O raises or the row was CONFLICT (defensive)."""
    path: str
    error: str  # English; UI translates if needed


@dataclass(frozen=True)
class PlanComplete:
    """Emitted exactly once at the end of apply_plan, with totals."""
    succeeded: int
    failed: int


ApplyEvent = Union[FileStarted, FileSucceeded, FileFailed, PlanComplete]


def read_bytes(path: Path) -> bytes | None:
    """Return raw file bytes, or ``None`` if the file does not exist.

    Raw means raw — line endings are preserved. Use
    :func:`read_bytes_normalized` for byte-equality comparisons.
    """
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


def read_bytes_normalized(path: Path) -> bytes | None:
    """Return bytes with ``\\r\\n`` collapsed to ``\\n``, or ``None`` if absent.

    Per ADR-0006: "Reads tolerate CRLF by normalizing to LF for comparison."
    Use this for any byte-equality decision; use :func:`read_bytes` when
    you need to preserve user content verbatim (e.g., appending to an
    existing CLAUDE.md).
    """
    raw = read_bytes(path)
    if raw is None:
        return None
    return raw.replace(b"\r\n", b"\n")


def atomic_write(path: Path, content: bytes) -> None:
    """Write ``content`` to ``path`` atomically; output is always LF.

    Mechanism: write to a sibling temp file with a random suffix, then
    ``os.replace`` it onto the destination. On a POSIX filesystem this
    is rename-atomic — a concurrent reader sees either the old file or
    the new one, never a torn intermediate.

    Side effects:
    - Parent directory is created if missing.
    - Any ``\\r\\n`` in ``content`` is normalized to ``\\n`` before write
      (output is always LF, per ADR-0006).
    - On exception, the temp file is removed before re-raising — no
      torn ``*.tmp`` artifacts left behind even on failure.
    """
    # LF-only output discipline per ADR-0006.
    content_lf = content.replace(b"\r\n", b"\n")
    path.parent.mkdir(parents=True, exist_ok=True)

    # Temp file lives in the same directory so os.replace is on the same
    # filesystem (POSIX rename atomicity requires this). Hidden + random
    # suffix keeps it out of accidental glob matches.
    suffix = secrets.token_hex(8)
    tmp_path = path.parent / f".{path.name}.{suffix}.tmp"

    try:
        with open(tmp_path, "wb") as f:
            f.write(content_lf)
        os.replace(tmp_path, path)
    except BaseException:
        # Belt-and-braces: ensure no orphaned tmp survives any failure
        # path. missing_ok=True tolerates the case where write itself
        # failed before the temp file was even created.
        tmp_path.unlink(missing_ok=True)
        raise


def apply_plan(
    plan: Plan,
    files: list[FileSpec],
    project_root: Path,
) -> Iterator[ApplyEvent]:
    """Walk ``plan.rows`` and apply each row's op, yielding events.

    Events emitted (per row, in order):

    - :class:`FileStarted` — always.
    - :class:`FileSucceeded` or :class:`FileFailed` — exactly one.

    After all rows: a single :class:`PlanComplete` with totals.

    Per ADR-0006 § Atomicity: a row's failure does NOT abort subsequent
    rows — the generator processes every row and surfaces successes
    and failures independently. The idempotent re-run discipline makes
    partial-apply states safe to recover from.

    For CONFLICT rows the function emits :class:`FileFailed` defensively
    rather than skipping silently — the UI layer (design 14 D3) is
    supposed to block apply when CONFLICTs are unresolved, but this
    function tolerates being called with them anyway.
    """
    # Build a path→spec index so per-row dispatch is O(1).
    spec_index: dict[str, FileSpec] = {spec.path: spec for spec in files}

    succeeded = 0
    failed = 0

    for row in plan.rows:
        path_str = row.path
        yield FileStarted(path=path_str)

        # Programmer-error guard: every PlanRow.path should appear in the
        # files list it was generated from.
        if path_str not in spec_index:
            yield FileFailed(path=path_str, error="No FileSpec for this path")
            failed += 1
            continue

        spec = spec_index[path_str]
        abs_path = project_root / path_str

        try:
            if row.op == Operation.CREATE:
                # ReplacementFile → write `rendered`. MergeableFile →
                # write `standalone_full` (markers + body).
                if isinstance(spec, ReplacementFile):
                    content = spec.rendered
                elif isinstance(spec, MergeableFile):
                    content = spec.standalone_full
                else:
                    yield FileFailed(
                        path=path_str, error="Unknown FileSpec type for CREATE"
                    )
                    failed += 1
                    continue

                atomic_write(abs_path, content)
                yield FileSucceeded(path=path_str, op=Operation.CREATE)
                succeeded += 1

            elif row.op == Operation.APPEND_DELIMITED:
                # MergeableFile only — splice the wrapped section onto
                # the END of the existing user content. Read raw so we
                # don't make line-ending decisions here; atomic_write
                # enforces LF on write per ADR-0006's "Output is always
                # LF" rule.
                if not isinstance(spec, MergeableFile):
                    yield FileFailed(
                        path=path_str,
                        error="Invalid FileSpec for APPEND_DELIMITED; expected MergeableFile",
                    )
                    failed += 1
                    continue

                existing = read_bytes(abs_path)
                if existing is None:
                    # Race / stale plan: file existed when plan was
                    # generated but is gone now. Refuse rather than
                    # invent a CREATE.
                    yield FileFailed(
                        path=path_str, error="Cannot append: target file does not exist"
                    )
                    failed += 1
                    continue

                version = spec.section_version
                body = spec.section_body.strip(b"\n")
                wrapped = (
                    b"<!-- maestro:start v=" + str(version).encode() + b" -->\n"
                    + body
                    + b"\n"
                    + b"<!-- maestro:end v=" + str(version).encode() + b" -->\n"
                )

                # Ensure exactly one blank line between user content
                # and our section, regardless of how the existing file
                # was terminated. Strip BOTH "\r" and "\n" from the
                # tail (rstrip with a byte set) so a CRLF-terminated
                # existing file doesn't leave a dangling \r before our
                # added "\n\n". atomic_write below normalizes any
                # remaining internal CRLF to LF (per ADR-0006), but
                # producing clean bytes upstream is the more honest
                # contract.
                new_content = existing.rstrip(b"\r\n") + b"\n\n" + wrapped

                atomic_write(abs_path, new_content)
                yield FileSucceeded(path=path_str, op=Operation.APPEND_DELIMITED)
                succeeded += 1

            elif row.op == Operation.NOOP:
                # By construction nothing on disk is touched.
                yield FileSucceeded(path=path_str, op=Operation.NOOP)
                succeeded += 1

            elif row.op == Operation.CONFLICT:
                # Defensive: UI should have blocked this. If we got
                # here anyway, surface as a failure rather than write.
                yield FileFailed(path=path_str, error="Conflict not resolved")
                failed += 1

            else:
                yield FileFailed(
                    path=path_str, error=f"Unknown operation: {row.op}"
                )
                failed += 1

        except Exception as exc:
            # Per-file isolation: any I/O exception becomes a FileFailed
            # event, and we continue with the next row.
            yield FileFailed(path=path_str, error=str(exc))
            failed += 1

    yield PlanComplete(succeeded=succeeded, failed=failed)
