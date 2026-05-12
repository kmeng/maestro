"""Unit tests for the problem panel view route (T3.9, Epic 3)."""

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from maestro.dispatch_log.events import (
    DispatchFailedEvent,
    DispatchFallbackConfigAbsentEvent,
    DispatchRefusedConfigInvalidEvent,
    DispatchStartEvent,
)
from maestro.webui.problem_panel import (
    _categorize,
    router as problem_router,
)


@pytest.fixture
def app():
    application = FastAPI()
    application.include_router(problem_router)
    return application


@pytest.fixture
def client(app):
    return TestClient(app)


def make_start_event(request_id="req1", role="coder", timestamp=None):
    ts = timestamp or datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    return DispatchStartEvent(
        event_version=1,
        request_id=request_id,
        timestamp=ts,
        role=role,
        model="gpt-4",
        member="member1",
        input_summary="hello",
    )


def make_failed_event(request_id="req1", error_kind="ModelError",
                      error_message="API offline", timestamp=None):
    ts = timestamp or datetime(2025, 1, 1, 12, 0, 10, tzinfo=timezone.utc)
    return DispatchFailedEvent(
        event_version=1,
        request_id=request_id,
        timestamp=ts,
        duration_ms=1200,
        error_kind=error_kind,
        error_message=error_message,
    )


def make_refused_event(request_id="req2", field="model", message="required", timestamp=None):
    ts = timestamp or datetime(2025, 1, 1, 12, 5, 0, tzinfo=timezone.utc)
    return DispatchRefusedConfigInvalidEvent(
        event_version=1,
        request_id=request_id,
        timestamp=ts,
        validation_error_field=field,
        validation_error_message=message,
    )


def make_fallback_event(request_id="req3", role="librarian", fallback_model="claude-3", timestamp=None):
    ts = timestamp or datetime(2025, 1, 1, 12, 10, 0, tzinfo=timezone.utc)
    return DispatchFallbackConfigAbsentEvent(
        event_version=1,
        request_id=request_id,
        timestamp=ts,
        role=role,
        fallback_model=fallback_model,
    )


def write_log(tmp_path, events):
    log_dir = tmp_path / ".maestro" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "dispatch.jsonl"
    with open(log_file, "w", encoding="utf-8") as f:
        for ev in events:
            f.write(ev.model_dump_json() + "\n")


def test_problems_empty_renders_reassurance(client, tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
    response = client.get("/problems")
    assert response.status_code == 200
    assert "暂无需要关注的问题" in response.text


def test_problems_failure_row_renders(client, tmp_path, monkeypatch):
    events = [
        make_start_event(request_id="abc"),
        make_failed_event(request_id="abc", error_kind="ModelError",
                          error_message="API offline"),
    ]
    write_log(tmp_path, events)
    monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
    response = client.get("/problems")
    assert response.status_code == 200
    text = response.text
    assert "失败的调度" in text
    assert "ModelError" in text
    assert "已知悉" in text


def test_problems_refusal_row_renders_with_cta(client, tmp_path, monkeypatch):
    events = [make_refused_event(field="model", message="required")]
    write_log(tmp_path, events)
    monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
    response = client.get("/problems")
    assert response.status_code == 200
    text = response.text
    assert "团队配置被拒" in text
    assert "model" in text
    assert "required" in text
    assert 'href="/team"' in text


def test_problems_fallback_grouped_with_cta(client, tmp_path, monkeypatch):
    events = [
        make_fallback_event(request_id="r1", role="librarian", fallback_model="claude-3"),
        make_fallback_event(request_id="r2", role="librarian", fallback_model="claude-3"),
        make_fallback_event(request_id="r3", role="librarian", fallback_model="claude-3"),
    ]
    write_log(tmp_path, events)
    monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
    response = client.get("/problems")
    assert response.status_code == 200
    text = response.text
    assert "3 次" in text
    assert "librarian" in text
    assert "claude-3" in text
    assert 'href="/wizard"' in text


def test_problems_fallback_groups_by_role_and_model(client, tmp_path, monkeypatch):
    events = [
        make_fallback_event(request_id="a", role="coder", fallback_model="A"),
        make_fallback_event(request_id="b", role="coder", fallback_model="A"),
        make_fallback_event(request_id="c", role="reviewer", fallback_model="B"),
    ]
    write_log(tmp_path, events)
    monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
    response = client.get("/problems")
    assert response.status_code == 200
    text = response.text
    assert text.count("次调度使用了降级模型") == 2
    assert "2 次" in text
    assert "1 次" in text


def test_problems_failure_attaches_role_from_start(client, tmp_path, monkeypatch):
    events = [
        make_start_event(request_id="X", role="coder"),
        make_failed_event(request_id="X"),
    ]
    write_log(tmp_path, events)
    monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
    response = client.get("/problems")
    assert response.status_code == 200
    assert "coder" in response.text


def test_problems_failure_without_start_uses_dash(client, tmp_path, monkeypatch):
    events = [make_failed_event(request_id="Y")]
    write_log(tmp_path, events)
    monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
    response = client.get("/problems")
    assert response.status_code == 200
    assert "—" in response.text


def test_problems_ack_button_pure_client(client, tmp_path, monkeypatch):
    events = [make_failed_event(request_id="Z")]
    write_log(tmp_path, events)
    monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
    response = client.get("/problems")
    assert response.status_code == 200
    text = response.text
    assert 'onclick="ackRow(this)"' in text
    assert "function ackRow" in text


def test_problems_categorize_unit():
    ts1 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    ts2 = datetime(2025, 1, 1, 12, 5, 0, tzinfo=timezone.utc)
    ts3 = datetime(2025, 1, 1, 12, 10, 0, tzinfo=timezone.utc)

    events = [
        make_start_event(request_id="A", role="coder", timestamp=ts1),
        make_failed_event(request_id="A", timestamp=ts1),
        make_refused_event(request_id="B", field="f", message="m", timestamp=ts2),
        make_fallback_event(request_id="C", role="coder", fallback_model="fb", timestamp=ts3),
        make_fallback_event(request_id="D", role="coder", fallback_model="fb", timestamp=ts3),
        make_fallback_event(request_id="E", role="reviewer", fallback_model="fb", timestamp=ts3),
    ]
    failures, refusals, groups = _categorize(events)
    assert len(failures) == 1
    assert failures[0].role == "coder"
    assert failures[0].error_kind == "ModelError"

    assert len(refusals) == 1
    assert refusals[0].validation_error_field == "f"

    assert len(groups) == 2
    groups.sort(key=lambda g: g.role)
    g1, g2 = groups
    assert g1.role == "coder" and g1.count == 2
    assert g2.role == "reviewer" and g2.count == 1
