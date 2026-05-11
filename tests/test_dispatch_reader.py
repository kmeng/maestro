"""
Unit tests for the dispatch log reader (T3.3).
"""

import os
import queue
import threading
import time
from datetime import datetime, timezone

import pytest

from maestro.dispatch_log.events import (
    DispatchEndEvent,
    DispatchFailedEvent,
    DispatchStartEvent,
)
from maestro.dispatch_log.reader import scan_log, tail_log


def _make_start(request_id: str, input_summary: str = "spec") -> DispatchStartEvent:
    return DispatchStartEvent(
        event_version=1,
        request_id=request_id,
        timestamp=datetime.now(timezone.utc),
        role="coder",
        model="deepseek-v4-pro",
        member="alice",
        input_summary=input_summary,
    )


def _make_end(request_id: str, output_summary: str = "ok") -> DispatchEndEvent:
    return DispatchEndEvent(
        event_version=1,
        request_id=request_id,
        timestamp=datetime.now(timezone.utc),
        output_summary=output_summary,
        duration_ms=42,
    )


def _make_failed(request_id: str, msg: str = "boom") -> DispatchFailedEvent:
    return DispatchFailedEvent(
        event_version=1,
        request_id=request_id,
        timestamp=datetime.now(timezone.utc),
        duration_ms=10,
        error_kind="Boom",
        error_message=msg,
    )


def _write_lines(path, *lines: str) -> None:
    with open(path, "ab") as f:
        for line in lines:
            f.write((line + "\n").encode("utf-8"))


def test_scan_log_returns_events_in_order(tmp_path):
    path = tmp_path / "dispatch.jsonl"
    ev1 = _make_start("1")
    ev2 = _make_end("1")
    ev3 = _make_failed("2")
    _write_lines(path, ev1.model_dump_json(), ev2.model_dump_json(), ev3.model_dump_json())

    result = scan_log(path)
    assert len(result) == 3
    assert isinstance(result[0], DispatchStartEvent)
    assert isinstance(result[1], DispatchEndEvent)
    assert isinstance(result[2], DispatchFailedEvent)
    assert result[0].request_id == "1"
    assert result[2].request_id == "2"


def test_scan_log_missing_file_returns_empty(tmp_path):
    assert scan_log(tmp_path / "nonexistent.jsonl") == []


def test_scan_log_empty_file_returns_empty(tmp_path):
    path = tmp_path / "empty.jsonl"
    path.write_text("")
    assert scan_log(path) == []


def test_scan_log_invalid_line_warns_and_skips(tmp_path, recwarn):
    path = tmp_path / "dispatch.jsonl"
    ev1 = _make_start("a")
    ev3 = _make_end("a")
    _write_lines(
        path,
        ev1.model_dump_json(),
        "not json",
        ev3.model_dump_json(),
    )

    result = scan_log(path)
    assert len(result) == 2
    assert result[0].request_id == "a"
    assert result[1].request_id == "a"

    assert any("unparseable" in str(w.message) for w in recwarn)
    assert any(issubclass(w.category, RuntimeWarning) for w in recwarn)


def _start_tail_thread(path, stop_event, poll_interval_s=0.05):
    q: queue.Queue = queue.Queue()

    def runner():
        for e in tail_log(path, poll_interval_s=poll_interval_s, stop_event=stop_event):
            q.put(e)

    t = threading.Thread(target=runner, daemon=True)
    t.start()
    return t, q


def test_tail_log_yields_new_events(tmp_path):
    path = tmp_path / "dispatch.jsonl"
    ev1 = _make_start("a")
    _write_lines(path, ev1.model_dump_json())

    stop = threading.Event()
    t, q = _start_tail_thread(path, stop)
    try:
        got1 = q.get(timeout=2.0)
        assert got1.request_id == "a"

        ev2 = _make_end("b")
        _write_lines(path, ev2.model_dump_json())

        got2 = q.get(timeout=2.0)
        assert got2.request_id == "b"
    finally:
        stop.set()
        t.join(timeout=2.0)


def test_tail_log_handles_rotation(tmp_path):
    path = tmp_path / "dispatch.jsonl"
    archive = tmp_path / "dispatch.archive.jsonl"

    ev_first = _make_start("first")
    _write_lines(path, ev_first.model_dump_json())

    stop = threading.Event()
    t, q = _start_tail_thread(path, stop)
    try:
        got1 = q.get(timeout=2.0)
        assert got1.request_id == "first"

        os.rename(path, archive)
        ev_second = _make_end("second")
        _write_lines(path, ev_second.model_dump_json())

        got2 = q.get(timeout=2.0)
        assert got2.request_id == "second"
    finally:
        stop.set()
        t.join(timeout=2.0)


def test_tail_log_skips_invalid_lines_and_continues(tmp_path, recwarn):
    path = tmp_path / "dispatch.jsonl"
    path.write_bytes(b"")

    stop = threading.Event()
    t, q = _start_tail_thread(path, stop)
    try:
        ev_valid = _make_start("ok")
        _write_lines(path, ev_valid.model_dump_json(), "junk", _make_end("ok2").model_dump_json())

        events = [q.get(timeout=2.0), q.get(timeout=2.0)]
        assert len(events) == 2
        assert events[0].request_id == "ok"
        assert events[1].request_id == "ok2"

        assert any("unparseable" in str(w.message) for w in recwarn)
    finally:
        stop.set()
        t.join(timeout=2.0)


def test_tail_log_holds_back_partial_line(tmp_path):
    path = tmp_path / "dispatch.jsonl"
    path.write_bytes(b"")

    stop = threading.Event()
    t, q = _start_tail_thread(path, stop, poll_interval_s=0.05)
    try:
        # Write a valid event's JSON without a trailing newline (partial).
        ev = _make_start("partial")
        json_bytes = ev.model_dump_json().encode("utf-8")
        path.write_bytes(json_bytes)  # no newline

        time.sleep(0.15)  # at least one poll cycle
        with pytest.raises(queue.Empty):
            q.get(timeout=0.1)

        # Now append the terminating newline.
        with open(path, "ab") as f:
            f.write(b"\n")

        got = q.get(timeout=2.0)
        assert got.request_id == "partial"
    finally:
        stop.set()
        t.join(timeout=2.0)


def test_tail_log_stops_on_stop_event(tmp_path):
    path = tmp_path / "dispatch.jsonl"
    path.write_bytes(b"")

    stop = threading.Event()
    t, q = _start_tail_thread(path, stop, poll_interval_s=0.05)
    stop.set()
    t.join(timeout=2.0)
    assert not t.is_alive()


def test_tail_log_waits_for_file_to_appear(tmp_path):
    path = tmp_path / "dispatch.jsonl"

    stop = threading.Event()
    t, q = _start_tail_thread(path, stop, poll_interval_s=0.05)
    try:
        time.sleep(0.2)
        ev = _make_start("late")
        _write_lines(path, ev.model_dump_json())
        got = q.get(timeout=2.0)
        assert got.request_id == "late"
    finally:
        stop.set()
        t.join(timeout=2.0)
