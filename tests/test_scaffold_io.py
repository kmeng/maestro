"""Unit tests for the scaffolding I/O layer (T2.2)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

import maestro.scaffold.io as io_module
from maestro.scaffold.io import (
    FileFailed,
    FileStarted,
    FileSucceeded,
    PlanComplete,
    apply_plan,
    atomic_write,
    read_bytes,
    read_bytes_normalized,
)
from maestro.scaffold.operations import (
    MergeableFile,
    Operation,
    Plan,
    PlanRow,
    ReplacementFile,
)


# -- atomic_write -----------------------------------------------------------

def test_atomic_write_creates_file_with_content(tmp_path: Path) -> None:
    target = tmp_path / "test.txt"
    atomic_write(target, b"hello")
    assert target.read_bytes() == b"hello"


def test_atomic_write_creates_parent_dir(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b" / "c.txt"
    atomic_write(target, b"nested")
    assert target.read_bytes() == b"nested"


def test_atomic_write_normalizes_crlf_to_lf(tmp_path: Path) -> None:
    target = tmp_path / "crlf.txt"
    atomic_write(target, b"a\r\nb\r\n")
    assert target.read_bytes() == b"a\nb\n"


def test_atomic_write_no_torn_tmp_left_behind(tmp_path: Path) -> None:
    target = tmp_path / "final.txt"
    atomic_write(target, b"content")
    # Only the final file should remain in tmp_path (no hidden tmp).
    children = list(tmp_path.iterdir())
    assert children == [target]


def test_atomic_write_overwrites_existing(tmp_path: Path) -> None:
    target = tmp_path / "overwrite.txt"
    target.write_bytes(b"first")
    atomic_write(target, b"second")
    assert target.read_bytes() == b"second"


# -- read helpers -----------------------------------------------------------

def test_read_bytes_returns_none_when_absent(tmp_path: Path) -> None:
    assert read_bytes(tmp_path / "nope.txt") is None


def test_read_bytes_returns_raw_bytes_including_crlf(tmp_path: Path) -> None:
    target = tmp_path / "raw.txt"
    target.write_bytes(b"a\r\nb")
    assert read_bytes(target) == b"a\r\nb"


def test_read_bytes_normalized_strips_crlf(tmp_path: Path) -> None:
    target = tmp_path / "norm.txt"
    target.write_bytes(b"a\r\nb\r\n")
    assert read_bytes_normalized(target) == b"a\nb\n"


# -- apply_plan -------------------------------------------------------------

def _plan(rows: list[PlanRow]) -> Plan:
    return Plan(rows=tuple(rows))


def test_apply_plan_create_replacement_file(tmp_path: Path) -> None:
    plan = _plan([PlanRow(path="f.txt", op=Operation.CREATE, detail="")])
    spec = ReplacementFile(path="f.txt", rendered=b"content")
    events = list(apply_plan(plan, [spec], tmp_path))
    assert events[0] == FileStarted(path="f.txt")
    assert events[1] == FileSucceeded(path="f.txt", op=Operation.CREATE)
    assert events[2] == PlanComplete(succeeded=1, failed=0)
    assert (tmp_path / "f.txt").read_bytes() == b"content"


def test_apply_plan_create_mergeable_file(tmp_path: Path) -> None:
    spec = MergeableFile(
        path="merge.txt",
        section_body=b"body",
        standalone_full=b"full",
        section_version=1,
    )
    plan = _plan([PlanRow(path="merge.txt", op=Operation.CREATE, detail="")])
    events = list(apply_plan(plan, [spec], tmp_path))
    assert FileSucceeded(path="merge.txt", op=Operation.CREATE) in events
    assert (tmp_path / "merge.txt").read_bytes() == b"full"


def test_apply_plan_append_delimited(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_bytes(b"user content\n")
    spec = MergeableFile(
        path="CLAUDE.md",
        section_body=b"added\n",
        standalone_full=b"ignored",
        section_version=1,
    )
    plan = _plan([PlanRow(path="CLAUDE.md", op=Operation.APPEND_DELIMITED, detail="")])
    events = list(apply_plan(plan, [spec], tmp_path))
    assert FileSucceeded(path="CLAUDE.md", op=Operation.APPEND_DELIMITED) in events
    content = (tmp_path / "CLAUDE.md").read_bytes()
    assert b"user content" in content
    assert b"<!-- maestro:start v=1 -->\nadded\n<!-- maestro:end v=1 -->\n" in content
    # Separator inserted exactly one blank line.
    assert b"user content\n\n<!-- maestro" in content


def test_apply_plan_append_to_crlf_terminated_file(tmp_path: Path) -> None:
    """Existing CLAUDE.md with CRLF line endings → output is clean LF.

    Reviewer-flagged bug (T2.2 review): old `rstrip(b"\\n")` left
    trailing `\\r` because rstrip only strips the chars in the byte
    set; on a CRLF-terminated existing file we'd produce
    `...\\r\\n\\n<!-- maestro...`. Fix: `rstrip(b"\\r\\n")` to strip
    both. atomic_write also normalizes CRLF→LF on write, so the
    on-disk bytes are clean either way — but the in-memory production
    must be clean too.
    """
    (tmp_path / "CLAUDE.md").write_bytes(b"user content\r\n")
    spec = MergeableFile(
        path="CLAUDE.md",
        section_body=b"added",
        standalone_full=b"ignored",
        section_version=1,
    )
    plan = _plan([PlanRow(path="CLAUDE.md", op=Operation.APPEND_DELIMITED, detail="")])
    list(apply_plan(plan, [spec], tmp_path))
    content = (tmp_path / "CLAUDE.md").read_bytes()
    # No CR anywhere — atomic_write enforces LF.
    assert b"\r" not in content
    # Exactly one blank line between user content and the marker, with
    # no orphaned bytes either side.
    assert b"user content\n\n<!-- maestro:start v=1 -->" in content
    assert b"user content\r" not in content
    assert b"\n\n\n" not in content


def test_apply_plan_append_to_file_without_trailing_newline(tmp_path: Path) -> None:
    """Existing file with no trailing newline at all → output is still
    correctly separated by exactly one blank line."""
    (tmp_path / "f").write_bytes(b"no newline at end")
    spec = MergeableFile(
        path="f",
        section_body=b"x",
        standalone_full=b"ignored",
        section_version=1,
    )
    plan = _plan([PlanRow(path="f", op=Operation.APPEND_DELIMITED, detail="")])
    list(apply_plan(plan, [spec], tmp_path))
    content = (tmp_path / "f").read_bytes()
    assert b"no newline at end\n\n<!-- maestro:start v=1 -->" in content
    assert b"\n\n\n" not in content


def test_apply_plan_append_preserves_existing_user_content(tmp_path: Path) -> None:
    original = b"some config\n"
    (tmp_path / "config").write_bytes(original)
    spec = MergeableFile(
        path="config",
        section_body=b"managed section\n",
        standalone_full=b"",
        section_version=2,
    )
    plan = _plan([PlanRow(path="config", op=Operation.APPEND_DELIMITED, detail="")])
    list(apply_plan(plan, [spec], tmp_path))
    assert (tmp_path / "config").read_bytes().startswith(original)


def test_apply_plan_noop_yields_succeeded_no_io(tmp_path: Path) -> None:
    target = tmp_path / "noop.txt"
    target.write_bytes(b"stay")
    mtime_before = os.path.getmtime(target)
    spec = ReplacementFile(path="noop.txt", rendered=b"unused")
    plan = _plan([PlanRow(path="noop.txt", op=Operation.NOOP, detail="")])
    events = list(apply_plan(plan, [spec], tmp_path))
    assert FileSucceeded(path="noop.txt", op=Operation.NOOP) in events
    assert target.read_bytes() == b"stay"
    assert os.path.getmtime(target) == mtime_before


def test_apply_plan_conflict_yields_failed(tmp_path: Path) -> None:
    spec = ReplacementFile(path="conflict.txt", rendered=b"")
    plan = _plan([PlanRow(path="conflict.txt", op=Operation.CONFLICT, detail="")])
    events = list(apply_plan(plan, [spec], tmp_path))
    assert FileFailed(path="conflict.txt", error="Conflict not resolved") in events
    assert not (tmp_path / "conflict.txt").exists()


def test_apply_plan_continues_after_per_file_failure(tmp_path: Path) -> None:
    spec1 = ReplacementFile(path="ok.txt", rendered=b"ok")
    spec2 = ReplacementFile(path="fail.txt", rendered=b"")
    spec3 = ReplacementFile(path="also_ok.txt", rendered=b"also")
    plan = _plan([
        PlanRow(path="ok.txt", op=Operation.CREATE, detail=""),
        PlanRow(path="fail.txt", op=Operation.CONFLICT, detail=""),
        PlanRow(path="also_ok.txt", op=Operation.CREATE, detail=""),
    ])
    events = list(apply_plan(plan, [spec1, spec2, spec3], tmp_path))
    successes = [e for e in events if isinstance(e, FileSucceeded)]
    failures = [e for e in events if isinstance(e, FileFailed)]
    assert len(successes) == 2
    assert len(failures) == 1
    assert events[-1] == PlanComplete(succeeded=2, failed=1)


def test_apply_plan_yields_failed_on_oserror(tmp_path: Path, monkeypatch) -> None:
    def mock_write(path, content):
        raise OSError("disk full")
    monkeypatch.setattr(io_module, "atomic_write", mock_write)
    spec = ReplacementFile(path="error.txt", rendered=b"boom")
    plan = _plan([PlanRow(path="error.txt", op=Operation.CREATE, detail="")])
    events = list(apply_plan(plan, [spec], tmp_path))
    failures = [e for e in events if isinstance(e, FileFailed)]
    assert len(failures) == 1
    assert "disk full" in failures[0].error


def test_apply_plan_event_order_per_row(tmp_path: Path) -> None:
    spec = ReplacementFile(path="order.txt", rendered=b"x")
    plan = _plan([PlanRow(path="order.txt", op=Operation.CREATE, detail="")])
    events = list(apply_plan(plan, [spec], tmp_path))
    row_types = [type(e) for e in events if not isinstance(e, PlanComplete)]
    assert row_types == [FileStarted, FileSucceeded]


def test_apply_plan_complete_counts(tmp_path: Path) -> None:
    spec_ok1 = ReplacementFile(path="ok1.txt", rendered=b"")
    spec_ok2 = ReplacementFile(path="ok2.txt", rendered=b"")
    spec_fail = ReplacementFile(path="fail.txt", rendered=b"")
    plan = _plan([
        PlanRow(path="ok1.txt", op=Operation.CREATE, detail=""),
        PlanRow(path="fail.txt", op=Operation.CONFLICT, detail=""),
        PlanRow(path="ok2.txt", op=Operation.CREATE, detail=""),
    ])
    events = list(apply_plan(plan, [spec_ok1, spec_ok2, spec_fail], tmp_path))
    assert events[-1] == PlanComplete(succeeded=2, failed=1)


# -- wiring -----------------------------------------------------------------

def test_webui_imports_scaffold_io() -> None:
    """T0.3's webui module must touch io so the module is loaded at startup."""
    from maestro.webui import _scaffold_io  # noqa: F401
    assert _scaffold_io is not None
