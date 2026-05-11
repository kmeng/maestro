"""Unit tests for the scaffolding engine (T2.1).

One test per ADR-0006 branch, plus CRLF / whitespace tolerance and plan
integrity checks. Pure-logic — no tmp_path, no filesystem.
"""
from __future__ import annotations

from maestro.scaffold import (
    ConflictReason,
    MergeableFile,
    Operation,
    ReplacementFile,
    generate_plan,
)


# -- ReplacementFile branches ------------------------------------------------

def test_replacement_absent_yields_create():
    spec = ReplacementFile(path="A", rendered=b"content")
    plan = generate_plan([spec], {"A": None})
    row = plan.rows[0]
    assert row.op == Operation.CREATE
    assert "A" in row.detail


def test_replacement_byte_match_yields_noop():
    content = b"same content"
    spec = ReplacementFile(path="A", rendered=content)
    plan = generate_plan([spec], {"A": content})
    assert plan.rows[0].op == Operation.NOOP


def test_replacement_differing_yields_conflict_replacement_differs():
    spec = ReplacementFile(path="A", rendered=b"hello")
    plan = generate_plan([spec], {"A": b"world"})
    row = plan.rows[0]
    assert row.op == Operation.CONFLICT
    assert row.conflict_reason == ConflictReason.REPLACEMENT_DIFFERS


def test_replacement_crlf_match_yields_noop():
    """Windows-style CRLF on disk vs LF in our rendered content → NOOP."""
    spec = ReplacementFile(path="A", rendered=b"line1\nline2\n")
    plan = generate_plan([spec], {"A": b"line1\r\nline2\r\n"})
    assert plan.rows[0].op == Operation.NOOP


# -- MergeableFile branches --------------------------------------------------

def test_mergeable_absent_yields_create():
    spec = MergeableFile(
        path="CLAUDE.md",
        section_body=b"hello",
        standalone_full=b"<!-- maestro:start v=1 -->\nhello\n<!-- maestro:end v=1 -->",
    )
    plan = generate_plan([spec], {"CLAUDE.md": None})
    row = plan.rows[0]
    assert row.op == Operation.CREATE
    assert "CLAUDE.md" in row.detail


def test_mergeable_no_marker_yields_append_delimited():
    spec = MergeableFile(
        path="CLAUDE.md",
        section_body=b"hello",
        standalone_full=b"full",
    )
    plan = generate_plan(
        [spec], {"CLAUDE.md": b"some user content without any maestro markers"}
    )
    assert plan.rows[0].op == Operation.APPEND_DELIMITED


def test_mergeable_v1_body_exact_match_yields_noop():
    spec = MergeableFile(
        path="CLAUDE.md",
        section_body=b"hello",
        standalone_full=b"full",
    )
    existing = b"<!-- maestro:start v=1 -->\nhello\n<!-- maestro:end v=1 -->"
    plan = generate_plan([spec], {"CLAUDE.md": existing})
    assert plan.rows[0].op == Operation.NOOP


def test_mergeable_v1_body_with_leading_trailing_whitespace_yields_noop():
    """Extra blank lines at section edges → strip → NOOP."""
    spec = MergeableFile(
        path="CLAUDE.md",
        section_body=b"hello",
        standalone_full=b"full",
    )
    existing = b"<!-- maestro:start v=1 -->\n\nhello\n\n<!-- maestro:end v=1 -->"
    plan = generate_plan([spec], {"CLAUDE.md": existing})
    assert plan.rows[0].op == Operation.NOOP


def test_mergeable_v1_body_with_internal_whitespace_difference_yields_conflict():
    """Extra blank line INSIDE the body (not at edges) → real edit → CONFLICT.

    Tolerance is leading/trailing only, per ADR-0006 explicit decision.
    """
    spec = MergeableFile(
        path="CLAUDE.md",
        section_body=b"line1\nline2",
        standalone_full=b"full",
    )
    existing = b"<!-- maestro:start v=1 -->\nline1\n\nline2\n<!-- maestro:end v=1 -->"
    plan = generate_plan([spec], {"CLAUDE.md": existing})
    row = plan.rows[0]
    assert row.op == Operation.CONFLICT
    assert row.conflict_reason == ConflictReason.DELIMITER_BODY_DIFFERS


def test_mergeable_v1_body_differs_yields_conflict_body_differs():
    spec = MergeableFile(
        path="CLAUDE.md",
        section_body=b"hello",
        standalone_full=b"full",
    )
    existing = b"<!-- maestro:start v=1 -->\ngoodbye\n<!-- maestro:end v=1 -->"
    plan = generate_plan([spec], {"CLAUDE.md": existing})
    row = plan.rows[0]
    assert row.op == Operation.CONFLICT
    assert row.conflict_reason == ConflictReason.DELIMITER_BODY_DIFFERS


def test_mergeable_vN_not_equal_section_version_yields_conflict_version_mismatch():
    spec = MergeableFile(
        path="CLAUDE.md",
        section_body=b"hello",
        standalone_full=b"full",
        section_version=1,
    )
    existing = b"<!-- maestro:start v=2 -->\nhello\n<!-- maestro:end v=2 -->"
    plan = generate_plan([spec], {"CLAUDE.md": existing})
    row = plan.rows[0]
    assert row.op == Operation.CONFLICT
    assert row.conflict_reason == ConflictReason.DELIMITER_VERSION_MISMATCH


def test_mergeable_multiple_start_markers_yields_conflict_multiple():
    spec = MergeableFile(
        path="CLAUDE.md",
        section_body=b"hello",
        standalone_full=b"full",
    )
    existing = (
        b"<!-- maestro:start v=1 -->\nhello1\n<!-- maestro:end v=1 -->\n"
        b"<!-- maestro:start v=1 -->\nhello2\n<!-- maestro:end v=1 -->"
    )
    plan = generate_plan([spec], {"CLAUDE.md": existing})
    row = plan.rows[0]
    assert row.op == Operation.CONFLICT
    assert row.conflict_reason == ConflictReason.MULTIPLE_DELIMITER_BLOCKS


def test_mergeable_unclosed_start_yields_conflict_unclosed():
    spec = MergeableFile(
        path="CLAUDE.md",
        section_body=b"hello",
        standalone_full=b"full",
    )
    existing = b"<!-- maestro:start v=1 -->\nhello\n"
    plan = generate_plan([spec], {"CLAUDE.md": existing})
    row = plan.rows[0]
    assert row.op == Operation.CONFLICT
    assert row.conflict_reason == ConflictReason.UNCLOSED_DELIMITER


def test_mergeable_crlf_existing_normalizes_for_comparison():
    spec = MergeableFile(
        path="CLAUDE.md",
        section_body=b"hello\nworld",
        standalone_full=b"full",
    )
    existing = b"<!-- maestro:start v=1 -->\r\nhello\r\nworld\r\n<!-- maestro:end v=1 -->"
    plan = generate_plan([spec], {"CLAUDE.md": existing})
    assert plan.rows[0].op == Operation.NOOP


# -- Plan integrity ----------------------------------------------------------

def test_plan_preserves_input_order():
    specs = [
        ReplacementFile(path="C", rendered=b"c"),
        ReplacementFile(path="A", rendered=b"a"),
        ReplacementFile(path="B", rendered=b"b"),
    ]
    existing = {"A": None, "B": None, "C": None}
    plan = generate_plan(specs, existing)
    assert [row.path for row in plan.rows] == ["C", "A", "B"]


def test_replacement_and_mergeable_in_same_plan():
    spec_rep = ReplacementFile(path="rep.txt", rendered=b"rep")
    spec_mer = MergeableFile(
        path="merge.md", section_body=b"sec", standalone_full=b"full"
    )
    plan = generate_plan([spec_rep, spec_mer], {"rep.txt": None, "merge.md": None})
    assert len(plan.rows) == 2
    assert plan.rows[0].path == "rep.txt"
    assert plan.rows[0].op == Operation.CREATE
    assert plan.rows[1].path == "merge.md"
    assert plan.rows[1].op == Operation.CREATE
