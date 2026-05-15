import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from maestro.webui import app
from maestro.dispatch_log.events import (
    DispatchStartEvent,
    DispatchFailedEvent,
    DispatchFallbackConfigAbsentEvent,
)
from maestro.savings import compute_costs


@pytest.fixture
def client():
    return TestClient(app)


def _patch_paths(monkeypatch, events_dir: Path, savings_path: Path, savings_source: str = "active"):
    """Patch both data-source functions overview_api uses.

    events_dir: a directory; the endpoint will look for `dispatch.jsonl` inside it.
    savings_path: a file path; passed straight to savings.read_rows_with_skipped.
    """
    monkeypatch.setattr(
        "maestro.webui.overview_api.paths.dispatch_log_path",
        lambda _cwd: events_dir,
    )
    monkeypatch.setattr(
        "maestro.webui.overview_api.resolve_log_path",
        lambda: (savings_path, savings_source),
    )


def test_overview_telemetry_disabled(client, tmp_path, monkeypatch):
    _patch_paths(monkeypatch, tmp_path, tmp_path / "savings.jsonl", savings_source="disabled")
    resp = client.get("/api/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["telemetry"] == "disabled"
    assert data["today"]["dispatches"] == 0
    assert data["today"]["savings_usd"] == 0.0
    assert data["today"]["delta_dispatches_vs_yesterday"] == 0
    assert data["cumulative"]["dispatches"] == 0
    assert data["cumulative"]["savings_usd"] == 0.0
    assert data["cumulative"]["savings_pct"] == 0.0
    assert data["now_running"] is None
    assert data["active_workers"] == 0
    assert data["open_problems"] == 0
    spark = data["sparkline_7d"]
    assert len(spark) == 7
    for entry in spark:
        assert entry["count"] == 0
    today_str = datetime.now(timezone.utc).date().isoformat()
    assert spark[-1]["date"] == today_str


def test_overview_empty_log(tmp_path, client, monkeypatch):
    events_dir = tmp_path
    (events_dir / "dispatch.jsonl").write_text("")
    savings = tmp_path / "savings.jsonl"
    savings.write_text("")
    _patch_paths(monkeypatch, events_dir, savings)

    resp = client.get("/api/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["telemetry"] == "active"
    assert data["today"]["dispatches"] == 0
    assert data["cumulative"]["dispatches"] == 0
    spark = data["sparkline_7d"]
    assert len(spark) == 7
    for entry in spark:
        assert entry["count"] == 0
    assert spark[-1]["date"] == datetime.now(timezone.utc).date().isoformat()


def test_overview_missing_file(client, tmp_path, monkeypatch):
    # Neither file exists.
    events_dir = tmp_path  # directory exists but no dispatch.jsonl inside
    savings = tmp_path / "__nonexistent__.jsonl"
    _patch_paths(monkeypatch, events_dir, savings)

    resp = client.get("/api/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["today"]["dispatches"] == 0
    assert data["cumulative"]["dispatches"] == 0
    assert data["now_running"] is None


def test_overview_happy_path(tmp_path, client, monkeypatch):
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)

    events = [
        DispatchStartEvent(
            request_id="req1",
            timestamp=now - timedelta(minutes=5),
            role="coder",
            model="deepseek-coder",
            member="ds-coder",
            input_summary="T9.2-test-1",
        ),
        DispatchStartEvent(
            request_id="req2",
            timestamp=now - timedelta(minutes=10),
            role="coder",
            model="deepseek-coder",
            member="ds-coder",
            input_summary="T9.2-test-2",
        ),
        DispatchStartEvent(
            request_id="req3",
            timestamp=yesterday,
            role="coder",
            model="deepseek-coder",
            member="ds-coder",
            input_summary="yesterday-1",
        ),
        DispatchStartEvent(
            request_id="req4",
            timestamp=yesterday,
            role="coder",
            model="deepseek-coder",
            member="ds-coder",
            input_summary="yesterday-2",
        ),
        DispatchFailedEvent(
            request_id="req-fail",
            timestamp=now - timedelta(hours=1),
            duration_ms=1000,
            error_kind="TestError",
            error_message="fail",
        ),
        DispatchFallbackConfigAbsentEvent(
            request_id="req-fb",
            timestamp=now - timedelta(hours=2),
            role="coder",
            fallback_model="fallback-model",
        ),
    ]

    events_dir = tmp_path / "events"
    events_dir.mkdir()
    with open(events_dir / "dispatch.jsonl", "w") as f:
        for ev in events:
            f.write(ev.model_dump_json() + "\n")

    savings = tmp_path / "savings.jsonl"
    savings.write_text("")  # no cost rows for this test
    _patch_paths(monkeypatch, events_dir, savings)

    resp = client.get("/api/overview")
    assert resp.status_code == 200
    data = resp.json()

    assert data["today"]["dispatches"] == 2
    assert data["cumulative"]["dispatches"] == 4
    assert data["open_problems"] == 2
    spark = data["sparkline_7d"]
    assert len(spark) == 7
    assert spark[-1]["count"] == 2, "Today entries missing"
    assert spark[-2]["count"] == 2, "Yesterday entries missing"
    assert spark[-1]["date"] == now.date().isoformat()


def test_overview_now_running_detected(tmp_path, client, monkeypatch):
    now = datetime.now(timezone.utc)
    start = DispatchStartEvent(
        request_id="run1",
        timestamp=now - timedelta(seconds=30),
        role="coder",
        model="deepseek-coder",
        member="ds-coder",
        input_summary="in-flight test",
    )
    events_dir = tmp_path / "events"
    events_dir.mkdir()
    with open(events_dir / "dispatch.jsonl", "w") as f:
        f.write(start.model_dump_json() + "\n")
    savings = tmp_path / "savings.jsonl"
    savings.write_text("")
    _patch_paths(monkeypatch, events_dir, savings)

    resp = client.get("/api/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["now_running"] is not None
    nr = data["now_running"]
    assert nr["role"] == "coder"
    assert 20 <= nr["elapsed_s"] <= 90  # generous window


def test_overview_stale_inflight_excluded(tmp_path, client, monkeypatch):
    now = datetime.now(timezone.utc)
    start = DispatchStartEvent(
        request_id="old1",
        timestamp=now - timedelta(seconds=1200),
        role="coder",
        model="deepseek-coder",
        member="ds-coder",
        input_summary="old",
    )
    events_dir = tmp_path / "events"
    events_dir.mkdir()
    with open(events_dir / "dispatch.jsonl", "w") as f:
        f.write(start.model_dump_json() + "\n")
    savings = tmp_path / "savings.jsonl"
    savings.write_text("")
    _patch_paths(monkeypatch, events_dir, savings)

    resp = client.get("/api/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["now_running"] is None
    assert data["active_workers"] == 0


def test_overview_superseded_excluded_from_savings(tmp_path, client, monkeypatch):
    now = datetime.now(timezone.utc)
    row1 = {
        "row_id": "r1",
        "schema_version": 1,
        "started_at": (now - timedelta(minutes=5)).isoformat(),
        "tool": "coder",
        "model": "deepseek-v4-flash",
        "model_provider": "deepseek",
        "prompt_tokens": 100,
        "completion_tokens": 200,
        "total_tokens": 300,
        "wall_s": 1.0,
        "is_estimate": False,
        "supersedes": None,
    }
    row2 = {
        "row_id": "r2",
        "schema_version": 1,
        "started_at": (now - timedelta(minutes=3)).isoformat(),
        "tool": "coder",
        "model": "deepseek-v4-flash",
        "model_provider": "deepseek",
        "prompt_tokens": 300,
        "completion_tokens": 400,
        "total_tokens": 700,
        "wall_s": 1.0,
        "is_estimate": False,
        "supersedes": "r1",
    }
    events_dir = tmp_path / "events"
    events_dir.mkdir()
    (events_dir / "dispatch.jsonl").write_text("")
    savings = tmp_path / "rows.jsonl"
    with open(savings, "w") as f:
        f.write(json.dumps(row1) + "\n")
        f.write(json.dumps(row2) + "\n")
    _patch_paths(monkeypatch, events_dir, savings)

    resp = client.get("/api/overview")
    assert resp.status_code == 200
    data = resp.json()

    expected_cost = compute_costs(row2)
    assert expected_cost is not None
    raw_saved = expected_cost.get("saved_usd", 0.0)
    raw_opus = expected_cost.get("opus_total_usd", 0.0)
    expected_saved_rounded = round(raw_saved, 2)
    # Production rounds savings_pct at the end using raw values, not display-rounded ones.
    expected_pct = round(raw_saved / raw_opus * 100, 1) if raw_opus else 0.0

    assert data["today"]["savings_usd"] == expected_saved_rounded
    assert data["cumulative"]["savings_usd"] == expected_saved_rounded
    assert data["cumulative"]["savings_pct"] == expected_pct
