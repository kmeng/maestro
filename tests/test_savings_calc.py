"""Pure-calc tests for bootstrap/savings.py.

Migrated from tests/test_render_savings.py per T7.1: the 4 pure-calc
tests (3 supersede + 1 null-tokens) moved here, plus new coverage for
_parse_dt (previously untested) and read_rows surface (previously only
tested via render_full).

The on-disk schema follows T6.2; helpers below build minimal valid rows.
"""

import json
from pathlib import Path

import pytest

from bootstrap.savings import (
    PROVIDER_RATES_USD_PER_M_TOKENS,
    _parse_dt,
    compute_costs,
    filter_superseded,
    group_by_role,
    group_by_task,
    read_rows,
)


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


def _enrich(row: dict) -> dict:
    """Add the same enrichment fields read_rows would, for tests that
    construct rows directly without going through read_rows.
    """
    enriched = dict(row)
    enriched["_started_at"] = _parse_dt(row["started_at"])
    enriched["_duration_seconds"] = float(row.get("wall_s") or 0.0)
    p = row.get("prompt_tokens")
    c = row.get("completion_tokens")
    t = row.get("total_tokens")
    if p is not None and c is not None:
        enriched["_token_count"] = int(p) + int(c)
    elif t is not None:
        enriched["_token_count"] = int(t)
    else:
        enriched["_token_count"] = 0
    enriched["_cost"] = compute_costs(row)
    return enriched


# ---------------------------------------------------------------------------
# _parse_dt
# ---------------------------------------------------------------------------

def test_parse_dt_trailing_z():
    """Trailing Z is converted to +00:00 for fromisoformat compat."""
    out = _parse_dt("2026-05-10T12:00:00Z")
    assert out.year == 2026
    assert out.hour == 12
    assert out.tzinfo is not None  # aware


def test_parse_dt_already_offset():
    """Explicit +00:00 passes through cleanly."""
    out = _parse_dt("2026-05-10T12:00:00+00:00")
    assert out.year == 2026
    assert out.hour == 12
    assert out.tzinfo is not None


def test_parse_dt_bad_input_raises():
    """Non-ISO-8601 input raises ValueError (propagates from fromisoformat)."""
    with pytest.raises(ValueError):
        _parse_dt("not-a-date")


# ---------------------------------------------------------------------------
# read_rows
# ---------------------------------------------------------------------------

def test_read_rows_missing_file_returns_empty(tmp_path: Path):
    """Nonexistent path → [] (no FileNotFoundError)."""
    assert read_rows(tmp_path / "nope.jsonl") == []


def test_read_rows_blank_file_returns_empty(tmp_path: Path):
    """Empty file → []."""
    jsonl = tmp_path / "empty.jsonl"
    jsonl.write_text("", encoding="utf-8")
    assert read_rows(jsonl) == []


def test_read_rows_skips_comments_and_blanks(tmp_path: Path):
    """`#`-prefixed and blank lines are ignored; real rows pass through."""
    jsonl = tmp_path / "comments.jsonl"
    _write_jsonl(jsonl, [
        "# header",
        "",
        json.dumps(_sample_row(row_id="a")),
        "  ",
        json.dumps(_sample_row(row_id="b")),
    ])
    rows = read_rows(jsonl)
    assert [r["row_id"] for r in rows] == ["a", "b"]


def test_read_rows_malformed_json_warns_and_skips(tmp_path: Path, capsys):
    """Bad JSON line → stderr warning + skip; subsequent valid lines parsed."""
    jsonl = tmp_path / "malformed.jsonl"
    _write_jsonl(jsonl, ["this is not json", json.dumps(_sample_row(row_id="good"))])
    rows = read_rows(jsonl)
    assert len(rows) == 1
    assert rows[0]["row_id"] == "good"
    assert "malformed JSON" in capsys.readouterr().err


def test_read_rows_schema_mismatch_warns_but_keeps(tmp_path: Path, capsys):
    """schema_version != 1 → warning to stderr but row is included."""
    jsonl = tmp_path / "schema.jsonl"
    _write_jsonl(jsonl, [json.dumps(_sample_row(schema_version=99))])
    rows = read_rows(jsonl)
    assert len(rows) == 1
    err = capsys.readouterr().err
    assert "schema_version 99" in err
    assert "!= expected 1" in err


def test_read_rows_bad_started_at_skips(tmp_path: Path, capsys):
    """Unparseable started_at → warning + skip."""
    jsonl = tmp_path / "bad_dt.jsonl"
    _write_jsonl(jsonl, [json.dumps(_sample_row(started_at="not-a-date"))])
    rows = read_rows(jsonl)
    assert rows == []
    assert "bad started_at" in capsys.readouterr().err


def test_read_rows_enrichment_fields_present(tmp_path: Path):
    """Each row gets _started_at (datetime), _duration_seconds (float), _token_count (int)."""
    jsonl = tmp_path / "ok.jsonl"
    _write_jsonl(jsonl, [json.dumps(
        _sample_row(wall_s=2.5, prompt_tokens=100, completion_tokens=50)
    )])
    rows = read_rows(jsonl)
    r = rows[0]
    assert hasattr(r["_started_at"], "year")
    assert r["_duration_seconds"] == 2.5
    assert r["_token_count"] == 150


def test_read_rows_token_count_fallback_to_total(tmp_path: Path):
    """When prompt/completion missing, _token_count falls back to total_tokens."""
    jsonl = tmp_path / "fallback.jsonl"
    _write_jsonl(jsonl, [json.dumps(
        _sample_row(prompt_tokens=None, completion_tokens=None, total_tokens=555)
    )])
    rows = read_rows(jsonl)
    assert rows[0]["_token_count"] == 555


def test_read_rows_token_count_zero_when_all_missing(tmp_path: Path):
    """No token info anywhere → _token_count = 0."""
    jsonl = tmp_path / "zero.jsonl"
    _write_jsonl(jsonl, [json.dumps(
        _sample_row(prompt_tokens=None, completion_tokens=None, total_tokens=None)
    )])
    rows = read_rows(jsonl)
    assert rows[0]["_token_count"] == 0


# ---------------------------------------------------------------------------
# filter_superseded (migrated from test_render_savings.py)
# ---------------------------------------------------------------------------

def test_supersede_excludes_original():
    """Row B with supersedes=A's row_id replaces A."""
    a = _sample_row(row_id="orig-1", task_id=None, issue_number=None)
    b = _sample_row(row_id="fix-1", task_id="T6.7", issue_number=63, supersedes="orig-1")
    survivors = filter_superseded([a, b])
    assert len(survivors) == 1
    assert survivors[0]["row_id"] == "fix-1"
    assert survivors[0]["task_id"] == "T6.7"


def test_supersede_chain_keeps_only_latest():
    """A → B → C: only C survives (transitive masking)."""
    a = _sample_row(row_id="a")
    b = _sample_row(row_id="b", supersedes="a")
    c = _sample_row(row_id="c", supersedes="b")
    survivors = filter_superseded([a, b, c])
    assert {r["row_id"] for r in survivors} == {"c"}


def test_supersede_with_unknown_target_keeps_supersede_row():
    """supersedes points at nonexistent row_id → supersede row stays."""
    b = _sample_row(row_id="b", supersedes="ghost")
    survivors = filter_superseded([b])
    assert len(survivors) == 1
    assert survivors[0]["row_id"] == "b"


# ---------------------------------------------------------------------------
# compute_costs
# ---------------------------------------------------------------------------

def test_compute_costs_unknown_model_returns_none():
    """Model not in PROVIDER_RATES → returns None (no raise)."""
    row = _sample_row(model="made-up-model")
    assert compute_costs(row) is None


def test_compute_costs_null_tokens_split_50_50():
    """prompt/completion null + total set → 50/50 split."""
    row = _sample_row(
        prompt_tokens=None, completion_tokens=None, total_tokens=100,
        model="claude-opus-4-7",
    )
    cost = compute_costs(row)
    # input=50, output=50 against opus rates 15/75 per M
    assert cost["worker_input_usd"] == pytest.approx(0.00075, rel=1e-6)
    assert cost["worker_output_usd"] == pytest.approx(0.00375, rel=1e-6)
    assert cost["worker_total_usd"] == pytest.approx(0.0045, rel=1e-6)


def test_compute_costs_both_tokens_present():
    """prompt+completion present → exact arithmetic against deepseek-v4-pro rates."""
    row = _sample_row(prompt_tokens=100, completion_tokens=50, total_tokens=150)
    cost = compute_costs(row)
    rates = PROVIDER_RATES_USD_PER_M_TOKENS["deepseek-v4-pro"]
    expected = (100 * rates["input"] + 50 * rates["output"]) / 1_000_000
    assert cost["worker_total_usd"] == pytest.approx(expected, rel=1e-9)


def test_compute_costs_zero_tokens():
    """All-zero tokens → all-zero cost dict; saved_pct = 0.0 (not NaN)."""
    row = _sample_row(prompt_tokens=0, completion_tokens=0, total_tokens=0)
    cost = compute_costs(row)
    assert cost["worker_total_usd"] == 0.0
    assert cost["opus_total_usd"] == 0.0
    assert cost["saved_usd"] == 0.0
    assert cost["saved_pct"] == 0.0


# ---------------------------------------------------------------------------
# group_by_task
# ---------------------------------------------------------------------------

def test_group_by_task_basic():
    """3 rows under same task_id → one group with count=3 and tool_counts sum correctly."""
    rows = [
        _enrich(_sample_row(row_id="r1", task_id="T0.4", tool="coder",
                            started_at="2026-01-01T10:00:00Z")),
        _enrich(_sample_row(row_id="r2", task_id="T0.4", tool="librarian",
                            started_at="2026-01-01T10:02:00Z")),
        _enrich(_sample_row(row_id="r3", task_id="T0.4", tool="reviewer",
                            started_at="2026-01-01T10:04:00Z")),
    ]
    groups = group_by_task(rows)
    assert len(groups) == 1
    g = groups[0]
    assert g["task_id"] == "T0.4"
    assert g["stats"]["count"] == 3
    assert g["stats"]["tool_counts"] == {"coder": 1, "librarian": 1, "reviewer": 1}


def test_group_by_task_unattributed_bucket():
    """task_id=None → 'unattributed' bucket; issue_number=None."""
    rows = [_enrich(_sample_row(row_id="u1", task_id=None, issue_number=None))]
    groups = group_by_task(rows)
    assert groups[0]["task_id"] == "unattributed"
    assert groups[0]["issue_number"] is None


def test_group_by_task_sort_issue_desc_then_unattributed_last():
    """Issues sort by -issue_number; None bucket trails."""
    rows = [
        _enrich(_sample_row(row_id="a", task_id="T1", issue_number=1,
                            started_at="2026-01-01T10:00:00Z")),
        _enrich(_sample_row(row_id="b", task_id="T5", issue_number=5,
                            started_at="2026-01-01T10:01:00Z")),
        _enrich(_sample_row(row_id="c", task_id="T3", issue_number=3,
                            started_at="2026-01-01T10:02:00Z")),
        _enrich(_sample_row(row_id="u", task_id=None, issue_number=None,
                            started_at="2026-01-01T09:00:00Z")),
    ]
    groups = group_by_task(rows)
    assert [g["issue_number"] for g in groups] == [5, 3, 1, None]


def test_group_by_task_rate_unknown_flag():
    """Row with unknown model → stats.has_rate_unknown=True."""
    row = _enrich(_sample_row(row_id="x", model="made-up-model"))
    groups = group_by_task([row])
    assert groups[0]["stats"]["has_rate_unknown"] is True


def test_group_by_task_estimate_flag():
    """is_estimate=True row → stats.has_estimate=True."""
    row = _enrich(_sample_row(row_id="e", is_estimate=True))
    groups = group_by_task([row])
    assert groups[0]["stats"]["has_estimate"] is True


# ---------------------------------------------------------------------------
# group_by_role
# ---------------------------------------------------------------------------

def test_group_by_role_returns_tuple():
    """Return type is (list, int) tuple — Web UI consumers rely on this."""
    rows = [_enrich(_sample_row())]
    result = group_by_role(rows)
    assert isinstance(result, tuple)
    assert len(result) == 2


def test_group_by_role_excludes_estimates():
    """is_estimate=True rows omitted from aggregation; excluded count reported."""
    rows = [
        _enrich(_sample_row(row_id="m1", tool="coder", is_estimate=False)),
        _enrich(_sample_row(row_id="m2", tool="coder", is_estimate=False)),
        _enrich(_sample_row(row_id="e1", tool="coder", is_estimate=True)),
    ]
    role_groups, excluded = group_by_role(rows)
    assert excluded == 1
    coder_group = next(g for g in role_groups if g["tool"] == "coder")
    assert coder_group["stats"]["count"] == 2


def test_group_by_role_sorted_alphabetical():
    """Roles returned in alphabetical tool name order — deterministic."""
    rows = [
        _enrich(_sample_row(row_id="1", tool="scribe")),
        _enrich(_sample_row(row_id="2", tool="coder")),
        _enrich(_sample_row(row_id="3", tool="reviewer")),
    ]
    role_groups, _ = group_by_role(rows)
    assert [g["tool"] for g in role_groups] == ["coder", "reviewer", "scribe"]


def test_group_by_role_stats_shape():
    """Each role group has the documented stats keys (Web UI consumer contract)."""
    rows = [
        _enrich(_sample_row(row_id="a", tool="coder", wall_s=2.0,
                            prompt_tokens=100, completion_tokens=50)),
        _enrich(_sample_row(row_id="b", tool="coder", wall_s=4.0,
                            prompt_tokens=200, completion_tokens=100)),
    ]
    role_groups, _ = group_by_role(rows)
    stats = role_groups[0]["stats"]
    assert stats["count"] == 2
    assert stats["total_tokens"] == 450
    assert stats["avg_tokens_per_call"] == 225
    assert stats["total_wall"] == 6.0
    assert stats["avg_wall"] == 3.0


# ---------------------------------------------------------------------------
# PROVIDER_RATES_USD_PER_M_TOKENS
# ---------------------------------------------------------------------------

def test_provider_rates_has_known_models():
    """Sanity: the 3 models documented in design 56 §4 are present."""
    assert "claude-opus-4-7" in PROVIDER_RATES_USD_PER_M_TOKENS
    assert "deepseek-v4-pro" in PROVIDER_RATES_USD_PER_M_TOKENS
    assert "deepseek-v4-flash" in PROVIDER_RATES_USD_PER_M_TOKENS
    for rates in PROVIDER_RATES_USD_PER_M_TOKENS.values():
        assert "input" in rates and "output" in rates
        assert isinstance(rates["input"], float)
        assert isinstance(rates["output"], float)
