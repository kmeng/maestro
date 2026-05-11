"""tests/test_dispatch_log_stream.py — SSE endpoint tests."""

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from maestro.dispatch_log.events import DispatchStartEvent
from maestro.dispatch_log.writer import emit_event
from maestro.webui import app


def _write_event(tmp_path: Path, request_id: str, summary: str) -> None:
    """Append one DispatchStartEvent to dispatch.jsonl."""
    ev = DispatchStartEvent(
        event_version=1,
        request_id=request_id,
        timestamp=datetime.now(timezone.utc),
        role="coder",
        model="deepseek-v4-pro",
        member="alice",
        input_summary=summary,
    )
    emit_event(ev, tmp_path)


@pytest.fixture
def client_with_cwd(tmp_path, monkeypatch):
    """Point Path.cwd() to tmp_path so dispatch.jsonl lives in test sandbox."""
    monkeypatch.setattr("maestro.webui.dispatch_log_api.Path.cwd", lambda: tmp_path)
    return TestClient(app)


@pytest.mark.skip(
    reason="TestClient.stream + EventSourceResponse blocks indefinitely; "
    "the infinite SSE stream is not friendly to the sync iter_lines() pattern. "
    "Real-stream behavior covered in T3.10 smoke (httpx async client via curl)."
)
def test_stream_yields_pre_existing_events(client_with_cwd, tmp_path):
    """If events exist when client connects, they should be delivered."""
    _write_event(tmp_path, "req-1", "test 1")
    _write_event(tmp_path, "req-2", "test 2")

    with client_with_cwd.stream("GET", "/api/dispatch_log/stream") as response:
        assert response.status_code == 200
        collected_data = []
        start = time.monotonic()
        for chunk in response.iter_lines():
            if "data:" in chunk and "dispatch.start" in chunk:
                data_str = chunk.split("data:", 1)[1].strip()
                event = json.loads(data_str)
                collected_data.append(event["request_id"])
                if len(collected_data) >= 2:
                    break
            if time.monotonic() - start > 3:
                break

        assert "req-1" in collected_data
        assert "req-2" in collected_data


@pytest.mark.skip(
    reason="Same TestClient + SSE limitation as test_stream_yields_pre_existing_events. "
    "Covered in T3.10 smoke."
)
def test_stream_yields_new_events_after_connect(client_with_cwd, tmp_path):
    """Events written after client connects should also appear."""

    def write_later():
        time.sleep(0.5)
        _write_event(tmp_path, "req-late", "late event")

    threading.Thread(target=write_later, daemon=True).start()

    with client_with_cwd.stream("GET", "/api/dispatch_log/stream") as response:
        collected = []
        start = time.monotonic()
        for chunk in response.iter_lines():
            if "data:" in chunk and "req-late" in chunk:
                collected.append(chunk)
                break
            if time.monotonic() - start > 5:
                break
        assert any("req-late" in c for c in collected)


def test_parse_last_event_id_valid():
    from maestro.webui.dispatch_log_api import _parse_last_event_id
    assert _parse_last_event_id("12345:678") == (12345, 678)


def test_parse_last_event_id_invalid():
    from maestro.webui.dispatch_log_api import _parse_last_event_id
    assert _parse_last_event_id(None) is None
    assert _parse_last_event_id("") is None
    assert _parse_last_event_id("malformed") is None
    assert _parse_last_event_id("a:b") is None


def test_stream_route_registered():
    """The /api/dispatch_log/stream route should be registered in the FastAPI app."""
    routes = [r.path for r in app.routes if hasattr(r, "path")]
    assert "/api/dispatch_log/stream" in routes
