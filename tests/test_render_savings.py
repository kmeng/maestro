"""Tests for scripts/render_savings.py.

Loaded via importlib because scripts/ is not a package (matches the
pattern used in tests/test_workers.py for bootstrap/maestro_server.py).

The schema mirrors the on-disk JSONL produced by `_emit_dispatch_row`
in bootstrap/maestro_server.py: required fields are `started_at`,
`wall_s`, `model`, `tool`, `total_tokens`, `is_estimate`,
`schema_version`. `prompt_tokens` / `completion_tokens` may be null.
"""

import importlib.util
import json
from pathlib import Path

import pytest


_THIS_FILE = Path(__file__).resolve()
_PROJECT_ROOT = _THIS_FILE.parent.parent
_SCRIPT_PATH = _PROJECT_ROOT / "scripts" / "render_savings.py"

_spec = importlib.util.spec_from_file_location("render_savings", _SCRIPT_PATH)
render_savings = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(render_savings)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_jsonl(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _sample_row(**overrides) -> dict:
    """Minimal valid dispatch row matching the T6.2 schema."""
    base = {
        "schema_version": 1,
        "row_id": "abcd-T1.0-coder-1",
        "task_id": "T1.0",
        "issue_number": 42,
        "tool": "coder",
        "model": "deepseek-v4-pro",
        "model_provider": "deepseek",
        "wall_s": 30.0,
        "prompt_tokens": 1000,
        "completion_tokens": 200,
        "total_tokens": 1200,
        "started_at": "2026-05-10T12:00:00Z",
        "journal_ref": None,
        "is_estimate": False,
        "est_method": None,
        "supersedes": None,
        "error": None,
    }
    base.update(overrides)
    return base


def _enrich(rows: list[dict]) -> list[dict]:
    for r in rows:
        r["_cost"] = render_savings.compute_costs(r)
    return rows


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_empty_jsonl_renders_placeholder():
    """Missing JSONL → empty rows → placeholder content."""
    content = render_savings.render_full([])
    assert "No measured dispatches yet" in content
    assert "Per-Task Savings" in content
    assert "Per-Role Breakdown" in content


def test_blank_jsonl_renders_placeholder(tmp_path: Path):
    """Blank lines only → empty rows → placeholder."""
    jsonl = tmp_path / "blank.jsonl"
    _write_jsonl(jsonl, ["", "  ", "\t"])
    rows = render_savings.read_rows(jsonl)
    assert rows == []
    content = render_savings.render_full(rows)
    assert "No measured dispatches yet" in content


def test_comments_are_skipped(tmp_path: Path):
    """`#`-prefixed lines are ignored; real rows still parsed."""
    jsonl = tmp_path / "with_comments.jsonl"
    line1 = "# this is a comment"
    line2 = json.dumps(_sample_row(task_id="T0.4"))
    _write_jsonl(jsonl, [line1, line2])
    rows = render_savings.read_rows(jsonl)
    assert len(rows) == 1
    rows = _enrich(rows)
    content = render_savings.render_full(rows)
    assert "1 dispatch" in content


def test_malformed_row_skipped_with_warning(capsys, tmp_path: Path):
    """Bad JSON is warned to stderr; valid rows survive."""
    jsonl = tmp_path / "malformed.jsonl"
    valid_line = json.dumps(_sample_row())
    bad_line = "this is not json"
    _write_jsonl(jsonl, [valid_line, bad_line])
    rows = render_savings.read_rows(jsonl)
    captured = capsys.readouterr().err
    assert "malformed JSON" in captured
    assert len(rows) == 1


def test_per_task_table_basic(tmp_path: Path):
    """3 rows under T0.4 (1 coder + 1 librarian + 1 reviewer) → '3 (c1 l1 r1 s0)'."""
    rows_raw = [
        _sample_row(task_id="T0.4", tool="coder",
                    started_at="2026-01-01T10:00:00Z", wall_s=60.0),
        _sample_row(task_id="T0.4", tool="librarian", model="deepseek-v4-flash",
                    started_at="2026-01-01T10:02:00Z", wall_s=60.0),
        _sample_row(task_id="T0.4", tool="reviewer",
                    started_at="2026-01-01T10:04:00Z", wall_s=60.0),
    ]
    jsonl = tmp_path / "task_table.jsonl"
    _write_jsonl(jsonl, [json.dumps(r) for r in rows_raw])
    rows = _enrich(render_savings.read_rows(jsonl))
    groups = render_savings.group_by_task(rows)
    table = render_savings.render_per_task_table(groups)
    assert "T0.4" in table
    assert "3 (c1 l1 r1 s0)" in table


def test_per_role_table_excludes_estimates(tmp_path: Path):
    """is_estimate=True rows excluded; footnote shows count."""
    rows_raw = [
        _sample_row(tool="coder", is_estimate=False),
        _sample_row(tool="coder", is_estimate=True, total_tokens=500),
    ]
    jsonl = tmp_path / "role_exclude.jsonl"
    _write_jsonl(jsonl, [json.dumps(r) for r in rows_raw])
    rows = _enrich(render_savings.read_rows(jsonl))
    rg, excl = render_savings.group_by_role(rows)
    assert excl == 1
    coder_group = [g for g in rg if g["tool"] == "coder"][0]
    assert coder_group["stats"]["count"] == 1
    table = render_savings.render_per_role_table(rg, excl)
    assert "1 row(s) excluded" in table


def test_unknown_model_marks_row(tmp_path: Path):
    """Unknown model → status cell shows 'rate-unknown ⚠'."""
    row_raw = _sample_row(model="made-up-model", task_id="T1")
    jsonl = tmp_path / "unknown.jsonl"
    _write_jsonl(jsonl, [json.dumps(row_raw)])
    rows = _enrich(render_savings.read_rows(jsonl))
    groups = render_savings.group_by_task(rows)
    table = render_savings.render_per_task_table(groups)
    assert "rate-unknown ⚠" in table


def test_null_tokens_split_50_50():
    """When prompt_tokens / completion_tokens null but total set: 50/50."""
    row = _sample_row(
        prompt_tokens=None,
        completion_tokens=None,
        total_tokens=100,
        model="claude-opus-4-7",
    )
    cost = render_savings.compute_costs(row)
    # input=50, output=50 against opus rates 15/75 per M
    assert cost["worker_input_usd"] == pytest.approx(0.00075, rel=1e-6)
    assert cost["worker_output_usd"] == pytest.approx(0.00375, rel=1e-6)
    assert cost["worker_total_usd"] == pytest.approx(0.0045, rel=1e-6)


def test_determinism_byte_identical_on_rerun(tmp_path: Path):
    """Rendering the same JSONL twice produces byte-identical output."""
    rows_raw = [_sample_row(task_id=f"T{i}", issue_number=100 + i) for i in range(3)]
    jsonl = tmp_path / "det.jsonl"
    _write_jsonl(jsonl, [json.dumps(r) for r in rows_raw])

    def render_once():
        rows = _enrich(render_savings.read_rows(jsonl))
        return render_savings.render_full(rows).encode("utf-8")

    assert render_once() == render_once()


def test_unattributed_bucket_for_null_task(tmp_path: Path):
    """task_id=None lands in 'unattributed' bucket; rendered as '—'."""
    row_raw = _sample_row(task_id=None, issue_number=None)
    jsonl = tmp_path / "unattrib.jsonl"
    _write_jsonl(jsonl, [json.dumps(row_raw)])
    rows = _enrich(render_savings.read_rows(jsonl))
    groups = render_savings.group_by_task(rows)
    assert groups[0]["task_id"] == "unattributed"
    table = render_savings.render_per_task_table(groups)
    # Task cell '— ' and issue cell ' — ' both present
    assert "| — " in table
    assert " — |" in table


def test_atomic_write_basic(tmp_path: Path):
    """Normal write produces no leftover .tmp file."""
    out = tmp_path / "output.md"
    render_savings.atomic_write(out, "hello")
    assert out.read_text() == "hello"
    assert not out.with_suffix(out.suffix + ".tmp").exists()
