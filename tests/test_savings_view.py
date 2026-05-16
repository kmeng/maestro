"""Route-level tests for GET /savings happy path (T7.3, Epic 7).

Empty / disabled / error states ship in T7.4 (#69); those route
branches return inline placeholder HTML for now.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from maestro.savings import (
    compute_costs,
    filter_superseded,
    group_by_role,
    group_by_time,
    read_rows,
)
from maestro.webui import app


@pytest.fixture
def client():
    return TestClient(app)


def _sample_row(**overrides) -> dict:
    base = {
        "schema_version": 1,
        "row_id": "view-test-1",
        "task_id": "T0.1",
        "issue_number": 1,
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


def _write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n",
        encoding="utf-8",
    )


def _seed_log(tmp_path: Path, monkeypatch) -> Path:
    """Write 3 rows spanning 2 UTC days + 2 tools; point env at the file."""
    log = tmp_path / "dispatch.jsonl"
    rows = [
        _sample_row(row_id="r1", tool="coder",
                    started_at="2026-05-10T08:00:00Z",
                    prompt_tokens=1000, completion_tokens=200, total_tokens=1200,
                    wall_s=10.0),
        _sample_row(row_id="r2", tool="reviewer",
                    started_at="2026-05-10T10:00:00Z",
                    prompt_tokens=500, completion_tokens=100, total_tokens=600,
                    wall_s=20.0),
        _sample_row(row_id="r3", tool="coder",
                    started_at="2026-05-11T15:00:00Z",
                    prompt_tokens=2000, completion_tokens=400, total_tokens=2400,
                    wall_s=30.0),
    ]
    _write_rows(log, rows)
    monkeypatch.setenv("MAESTRO_DISPATCH_LOG", str(log))
    return log


def test_savings_happy_path_renders_200(client, tmp_path, monkeypatch):
    """Mixed rows, telemetry enabled, JSONL exists → 200 + savings.html sections."""
    log = _seed_log(tmp_path, monkeypatch)
    resp = client.get("/savings")
    assert resp.status_code == 200
    body = resp.text
    # Title + section headers (redesigned page T9.9 uses "Savings" h1 only)
    assert ">Savings</h1>" in body
    assert "Per-role" in body
    assert "Per-time" in body
    # Headline reflects 3 dispatches across the 2-day range (new design renders
    # the count inside a .kpi-value div rather than the legacy <strong>).
    assert ">3<" in body
    assert "dispatch" in body
    assert "2026-05-10" in body
    assert "2026-05-11" in body
    # Footer shows path + telemetry-enabled
    assert str(log) in body
    assert "Telemetry" in body
    assert "enabled" in body


def test_savings_per_role_cells_match_calc(client, tmp_path, monkeypatch):
    """Numbers in the rendered HTML match direct calc-layer calls (shared layer)."""
    log = _seed_log(tmp_path, monkeypatch)
    resp = client.get("/savings")
    body = resp.text

    rows = filter_superseded(read_rows(log))
    for r in rows:
        r["_cost"] = compute_costs(r)
    role_groups, _excluded = group_by_role(rows)

    # Coder row: 2 dispatches, tokens = 1200 + 2400 = 3600
    coder = next(g for g in role_groups if g["tool"] == "coder")
    assert coder["stats"]["count"] == 2
    assert coder["stats"]["total_tokens"] == 3600
    # Total tokens formatted with thousands separator
    assert "3,600" in body
    # Reviewer row: 1 dispatch, tokens = 600
    reviewer = next(g for g in role_groups if g["tool"] == "reviewer")
    assert reviewer["stats"]["total_tokens"] == 600


def test_savings_per_time_reverse_chrono(client, tmp_path, monkeypatch):
    """Per-time table renders both days; newer day appears before older in HTML."""
    _seed_log(tmp_path, monkeypatch)
    resp = client.get("/savings")
    body = resp.text

    idx_11 = body.find("2026-05-11")
    idx_10 = body.find("2026-05-10")
    # Both dates present
    assert idx_11 != -1 and idx_10 != -1
    # The DATE CELL of 11 comes before the date cell of 10 inside the per-time
    # table. (10 also appears earlier in the headline, so we check the table
    # region — slice from the "Per-time" heading onward.)
    pt_idx = body.find("Per-time")
    assert pt_idx != -1
    sub = body[pt_idx:]
    assert sub.find("2026-05-11") < sub.find("2026-05-10")


def test_savings_disabled_renders_banner(client, monkeypatch):
    """MAESTRO_DISPATCH_LOG="" → 200 + savings_disabled.html banner."""
    monkeypatch.setenv("MAESTRO_DISPATCH_LOG", "")
    resp = client.get("/savings")
    assert resp.status_code == 200
    body = resp.text
    assert "Telemetry is disabled" in body
    assert "MAESTRO_DISPATCH_LOG" in body
    # Methodology link present
    assert "savings-methodology.md" in body


def test_savings_empty_renders_cta(client, tmp_path, monkeypatch):
    """Path resolves but file does not exist → 200 + savings_empty.html CTA."""
    nonexistent = tmp_path / "no-such.jsonl"
    monkeypatch.setenv("MAESTRO_DISPATCH_LOG", str(nonexistent))
    resp = client.get("/savings")
    assert resp.status_code == 200
    body = resp.text
    assert "No dispatches recorded yet" in body
    # CTA mentions the 4 worker roles
    assert "coder" in body and "librarian" in body and "reviewer" in body and "scribe" in body
    # Path is surfaced for transparency
    assert str(nonexistent) in body


def test_savings_error_renders_diagnostic(client, tmp_path, monkeypatch):
    """Path points at a directory → read raises IsADirectoryError → 200 + error template."""
    bad_path = tmp_path / "is-a-dir"
    bad_path.mkdir()
    monkeypatch.setenv("MAESTRO_DISPATCH_LOG", str(bad_path))
    resp = client.get("/savings")
    assert resp.status_code == 200
    body = resp.text
    # Redesigned error template (T9.9) uses Chinese title "无法读取 dispatch 日志".
    assert "无法读取 dispatch 日志" in body or "Could not read the dispatch log" in body
    assert str(bad_path) in body
    # Some form of the underlying exception text should appear in the <pre> block
    assert "directory" in body.lower() or "errno" in body.lower()


def test_savings_malformed_rows_footnote(client, tmp_path, monkeypatch):
    """Mixed valid + malformed rows → happy template + 'N malformed row(s) skipped' footnote."""
    log = tmp_path / "mixed.jsonl"
    valid_row = _sample_row(row_id="ok", started_at="2026-05-10T08:00:00Z")
    lines = [
        json.dumps(valid_row),
        "this-is-not-json",
        json.dumps(_sample_row(row_id="bad-dt", started_at="garbage")),
    ]
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    monkeypatch.setenv("MAESTRO_DISPATCH_LOG", str(log))
    resp = client.get("/savings")
    assert resp.status_code == 200
    body = resp.text
    # Happy template still rendered (the 1 valid row produces real content)
    assert ">Savings</h1>" in body
    assert "Per-role" in body
    # Footnote with the skipped count (2 = JSON-decode + bad-started_at)
    assert "2 malformed rows skipped" in body
