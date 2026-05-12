"""Unit tests for the history view route (T3.7, Epic 3)."""

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from maestro.dispatch_log.events import (
    CostBreakdown,
    DispatchEndEvent,
    DispatchFailedEvent,
    DispatchFallbackConfigAbsentEvent,
    DispatchRefusedConfigInvalidEvent,
    DispatchStartEvent,
)
from maestro.webui.history_view import (
    HistoryRow,
    _build_row,
    _fold_events,
    router as history_router,
)


@pytest.fixture
def app():
    application = FastAPI()
    application.include_router(history_router)
    return application


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def mock_cwd(tmp_path, monkeypatch):
    """Redirect Path.cwd() to tmp_path and create .maestro/logs directory."""
    (tmp_path / ".maestro" / "logs").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
    return tmp_path


def _write_log(log_path: Path, events: list) -> None:
    with open(log_path, "w", encoding="utf-8") as f:
        for ev in events:
            f.write(ev.model_dump_json() + "\n")


def test_history_empty_renders_empty_state(client, mock_cwd):
    response = client.get("/history")
    assert response.status_code == 200
    assert "暂无调度记录" in response.text


def test_history_renders_success_row(client, mock_cwd):
    now = datetime(2026, 5, 12, 14, 23, 11, tzinfo=timezone.utc)
    start = DispatchStartEvent(
        request_id="r1",
        timestamp=now,
        role="coder",
        model="deepseek-coder",
        member="Jamie",
        input_summary="Implement feature A",
    )
    cost = CostBreakdown(prompt_tokens=230, completion_tokens=1420, usd=None)
    end = DispatchEndEvent(
        request_id="r1",
        timestamp=now,
        output_summary="Done",
        duration_ms=1500,
        cost=cost,
    )
    log_path = mock_cwd / ".maestro" / "logs" / "dispatch.jsonl"
    _write_log(log_path, [start, end])

    response = client.get("/history")
    assert response.status_code == 200
    text = response.text
    assert "成功" in text
    assert "✓" in text
    assert "Implement feature A" in text
    assert "1.5 秒" in text
    assert "coder / Jamie" in text
    assert "deepseek-coder" in text


def test_history_renders_failed_row(client, mock_cwd):
    now = datetime(2026, 5, 12, 14, 30, 0, tzinfo=timezone.utc)
    start = DispatchStartEvent(
        request_id="r2",
        timestamp=now,
        role="reviewer",
        model="gpt-4o",
        member="Alex",
        input_summary="Review PR",
    )
    failed = DispatchFailedEvent(
        request_id="r2",
        timestamp=now,
        duration_ms=230,
        error_kind="TimeoutError",
        error_message="Request timed out after 30s",
    )
    log_path = mock_cwd / ".maestro" / "logs" / "dispatch.jsonl"
    _write_log(log_path, [start, failed])

    response = client.get("/history")
    assert response.status_code == 200
    text = response.text
    assert "失败" in text
    assert "✗" in text
    assert "TimeoutError" in text
    assert "Request timed out" in text
    assert "230 毫秒" in text
    assert "reviewer / Alex" in text
    assert "gpt-4o" in text


def test_history_renders_refused_row(client, mock_cwd):
    now = datetime(2026, 5, 12, 15, 0, 0, tzinfo=timezone.utc)
    refused = DispatchRefusedConfigInvalidEvent(
        request_id="r3",
        timestamp=now,
        validation_error_field="model",
        validation_error_message="Invalid model name",
    )
    log_path = mock_cwd / ".maestro" / "logs" / "dispatch.jsonl"
    _write_log(log_path, [refused])

    response = client.get("/history")
    assert response.status_code == 200
    text = response.text
    assert "已拒绝" in text
    assert "⊘" in text
    assert "Invalid model name" in text
    assert "校验字段" in text
    assert "—" in text


def test_history_attaches_fallback_badge(client, mock_cwd):
    now = datetime(2026, 5, 12, 16, 0, 0, tzinfo=timezone.utc)
    fallback = DispatchFallbackConfigAbsentEvent(
        request_id="r4",
        timestamp=now,
        role="coder",
        fallback_model="cheap-model",
    )
    start = DispatchStartEvent(
        request_id="r4",
        timestamp=now,
        role="coder",
        model="cheap-model",
        member="Jamie",
        input_summary="Do task B",
    )
    end = DispatchEndEvent(
        request_id="r4",
        timestamp=now,
        output_summary="Done cheap",
        duration_ms=500,
        cost=None,
    )
    log_path = mock_cwd / ".maestro" / "logs" / "dispatch.jsonl"
    _write_log(log_path, [fallback, start, end])

    response = client.get("/history")
    assert response.status_code == 200
    text = response.text
    assert "已降级" in text
    assert "成功" in text
    assert "✓" in text
    assert "badge-fallback" in text


def test_history_reverse_chronological(client, mock_cwd):
    t1 = datetime(2026, 5, 12, 10, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 5, 12, 12, 0, 0, tzinfo=timezone.utc)
    t3 = datetime(2026, 5, 12, 18, 0, 0, tzinfo=timezone.utc)

    ev1 = DispatchStartEvent(
        request_id="r_t1", timestamp=t1, role="coder", model="m", member="a", input_summary="first"
    )
    end1 = DispatchEndEvent(
        request_id="r_t1", timestamp=t1, output_summary="ok", duration_ms=100, cost=None
    )
    ev2 = DispatchStartEvent(
        request_id="r_t2", timestamp=t2, role="reviewer", model="m", member="b", input_summary="second"
    )
    end2 = DispatchEndEvent(
        request_id="r_t2", timestamp=t2, output_summary="ok", duration_ms=200, cost=None
    )
    ev3 = DispatchStartEvent(
        request_id="r_t3", timestamp=t3, role="reviewer", model="m", member="c", input_summary="third"
    )
    end3 = DispatchEndEvent(
        request_id="r_t3", timestamp=t3, output_summary="ok", duration_ms=300, cost=None
    )
    log_path = mock_cwd / ".maestro" / "logs" / "dispatch.jsonl"
    _write_log(log_path, [ev1, end1, ev2, end2, ev3, end3])

    response = client.get("/history")
    assert response.status_code == 200
    text = response.text
    assert text.index("third") < text.index("first")


def test_history_truncation_marker(client, mock_cwd):
    long_input = "A" * 75
    now = datetime(2026, 5, 12, 14, 0, 0, tzinfo=timezone.utc)
    start = DispatchStartEvent(
        request_id="r5",
        timestamp=now,
        role="reviewer",
        model="m",
        member="u",
        input_summary=long_input,
    )
    end = DispatchEndEvent(
        request_id="r5",
        timestamp=now,
        output_summary="out",
        duration_ms=50,
        cost=None,
    )
    log_path = mock_cwd / ".maestro" / "logs" / "dispatch.jsonl"
    _write_log(log_path, [start, end])

    response = client.get("/history")
    assert response.status_code == 200
    text = response.text
    assert long_input[:60] in text
    assert "…" in text
    assert "（已截断）" in text


def test_fold_events_empty():
    assert _fold_events([]) == []


def test_fold_events_unit():
    now = datetime(2026, 5, 12, 15, 0, 0, tzinfo=timezone.utc)
    start1 = DispatchStartEvent(
        request_id="req1", timestamp=now, role="coder", model="m1", member="a", input_summary="do X"
    )
    end1 = DispatchEndEvent(
        request_id="req1", timestamp=now, output_summary="done", duration_ms=100, cost=None
    )
    fail = DispatchFailedEvent(
        request_id="req2", timestamp=now, duration_ms=50, error_kind="E", error_message="err"
    )
    refused = DispatchRefusedConfigInvalidEvent(
        request_id="req3", timestamp=now, validation_error_field="f", validation_error_message="bad"
    )
    rows = _fold_events([start1, end1, fail, refused])
    assert len(rows) == 3
    assert {r.status for r in rows} == {"success", "failed", "refused"}
