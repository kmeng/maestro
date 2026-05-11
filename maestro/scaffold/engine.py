from __future__ import annotations

import re
from typing import Mapping

from .operations import (
    ConflictReason,
    FileSpec,
    MergeableFile,
    Operation,
    Plan,
    PlanRow,
    ReplacementFile,
)

# Delimiter format is load-bearing per ADR-0005 — `<!-- maestro:start v=N -->`
# / `<!-- maestro:end v=N -->`. Once user projects carry these markers in
# the wild, changing the syntax requires migration code (find-and-rewrite).
# We match bytes (not str) so the engine stays I/O-free and CRLF-tolerant
# downstream.
START_RE = re.compile(rb"<!-- maestro:start v=(\d+) -->")
END_RE = re.compile(rb"<!-- maestro:end v=(\d+) -->")


def _normalize_crlf(b: bytes) -> bytes:
    """Replace CRLF with LF for content comparison.

    ADR-0006 mandates "Reads tolerate CRLF by normalizing to LF for
    comparison" so a Windows-checkout-of-an-LF-template doesn't get
    flagged as a CONFLICT. Output is always LF (apply executor's job, not
    ours), but reads accept either.
    """
    return b.replace(b"\r\n", b"\n")


def _parse_maestro_section(existing_bytes: bytes) -> tuple[int, bytes] | str:
    """Locate the (single) Maestro section in `existing_bytes`.

    Returns:
        (version, body_between_markers) on success — exactly one start
        marker, with a matching end marker for the same version.
        ``'absent'``    — no start marker found.
        ``'multiple'``  — two or more start markers (corruption / unsupported).
        ``'unclosed'``  — start marker present, no matching end with same N.

    The body is the raw bytes between the end of the start marker and
    the start of the end marker — caller normalizes / strips as needed.
    """
    starts = list(START_RE.finditer(existing_bytes))
    if not starts:
        return "absent"
    if len(starts) > 1:
        return "multiple"
    start_m = starts[0]
    start_v = int(start_m.group(1))
    for end_m in END_RE.finditer(existing_bytes, pos=start_m.end()):
        if int(end_m.group(1)) == start_v:
            body = existing_bytes[start_m.end():end_m.start()]
            return (start_v, body)
    return "unclosed"


def generate_plan(
    files: list[FileSpec],
    existing: Mapping[str, bytes | None],
) -> Plan:
    """Generate a Plan describing the op for each FileSpec given destination state.

    `existing` maps the same path strings used in FileSpec.path to either the
    file's current bytes (if it exists on disk) or None (if it doesn't).
    The engine is pure — actual filesystem reads happen in T2.2's apply
    layer and feed the result here.

    Returns a Plan whose rows preserve the input order of `files`.
    """
    rows: list[PlanRow] = []
    for spec in files:
        if isinstance(spec, ReplacementFile):
            rows.append(_handle_replacement(spec, existing))
        elif isinstance(spec, MergeableFile):
            rows.append(_handle_mergeable(spec, existing))
        else:
            raise AssertionError(f"Unknown FileSpec type: {type(spec)}")
    return Plan(rows=tuple(rows))


def _handle_replacement(
    spec: ReplacementFile, existing: Mapping[str, bytes | None]
) -> PlanRow:
    path = spec.path
    existing_bytes = existing.get(path)
    if existing_bytes is None:
        # Destination doesn't exist — safe to write our rendered content.
        return PlanRow(
            path=path,
            op=Operation.CREATE,
            detail=f"将创建 {path}",
        )
    # CRLF-tolerant comparison — a file checked out on Windows with `\r\n`
    # endings is equivalent to its LF source for idempotence purposes.
    if _normalize_crlf(existing_bytes) == _normalize_crlf(spec.rendered):
        return PlanRow(
            path=path,
            op=Operation.NOOP,
            detail="已是最新内容",
        )
    # File exists and differs — user has a custom version. Maestro never
    # replaces silently; surface it as a conflict for the user to decide.
    return PlanRow(
        path=path,
        op=Operation.CONFLICT,
        detail="文件已存在且内容不同",
        conflict_reason=ConflictReason.REPLACEMENT_DIFFERS,
    )


def _handle_mergeable(
    spec: MergeableFile, existing: Mapping[str, bytes | None]
) -> PlanRow:
    path = spec.path
    existing_bytes = existing.get(path)

    if existing_bytes is None:
        # No host file — write the full standalone form (markers + body).
        return PlanRow(
            path=path,
            op=Operation.CREATE,
            detail=f"将创建 {path}",
        )

    parse_result = _parse_maestro_section(existing_bytes)
    if parse_result == "absent":
        # Host file exists but has no Maestro section yet — append ours
        # with the delimiters.
        return PlanRow(
            path=path,
            op=Operation.APPEND_DELIMITED,
            detail="将追加 Maestro 区段",
        )
    if parse_result == "multiple":
        # Corruption / unsupported state: refuse rather than guess which
        # of multiple sections is canonical.
        return PlanRow(
            path=path,
            op=Operation.CONFLICT,
            detail="文件中存在多个 Maestro 起始标记",
            conflict_reason=ConflictReason.MULTIPLE_DELIMITER_BLOCKS,
        )
    if parse_result == "unclosed":
        # Hand-edit left the section unterminated. Refuse rather than
        # try to fix structural damage.
        return PlanRow(
            path=path,
            op=Operation.CONFLICT,
            detail="Maestro 区段未正确闭合",
            conflict_reason=ConflictReason.UNCLOSED_DELIMITER,
        )

    existing_version, existing_body = parse_result  # type: ignore[misc]
    if existing_version != spec.section_version:
        # Older or newer Maestro section version. v0.0.3 ships v=1 only;
        # no auto-migration. The user (or a future migrator) updates.
        return PlanRow(
            path=path,
            op=Operation.CONFLICT,
            detail=f"Maestro 区段版本不匹配 (v={existing_version})",
            conflict_reason=ConflictReason.DELIMITER_VERSION_MISMATCH,
        )

    # Same version — compare body bytes. Tolerate ONLY leading/trailing
    # whitespace (per ADR-0006 — internal whitespace differences are real
    # edits the user might rely on, not noise we can paper over).
    if _normalize_crlf(existing_body).strip() == _normalize_crlf(spec.section_body).strip():
        return PlanRow(
            path=path,
            op=Operation.NOOP,
            detail="已是最新区段",
        )
    return PlanRow(
        path=path,
        op=Operation.CONFLICT,
        detail="Maestro 区段内容已被修改",
        conflict_reason=ConflictReason.DELIMITER_BODY_DIFFERS,
    )
