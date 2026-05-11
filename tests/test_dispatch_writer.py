"""
Unit tests for the dispatch log writer (T3.2).
"""

import os
import sys
import subprocess as _subprocess_module
from datetime import datetime, timezone
from pathlib import Path

import pytest

from maestro.dispatch_log.events import DispatchStartEvent, DISPATCH_EVENT_ADAPTER
from maestro.dispatch_log.truncation import truncate_event
from maestro.dispatch_log.writer import emit_event

_REAL_SUBPROCESS_RUN = _subprocess_module.run
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _make_event(request_id="req-1", input_summary="hello world") -> DispatchStartEvent:
    return DispatchStartEvent(
        event_version=1,
        request_id=request_id,
        timestamp=datetime.now(timezone.utc),
        role="coder",
        model="deepseek-v4-pro",
        member="alice",
        input_summary=input_summary,
    )


def test_emit_writes_one_jsonl_line(tmp_path):
    event = _make_event()
    emit_event(event, tmp_path)

    log_file = tmp_path / ".maestro" / "logs" / "dispatch.jsonl"
    assert log_file.exists()

    data = log_file.read_bytes()
    assert data.endswith(b"\n")

    lines = [l for l in data.split(b"\n") if l]
    assert len(lines) == 1

    line = lines[0]
    assert len(line) <= 4096

    parsed = DISPATCH_EVENT_ADAPTER.validate_json(line)
    assert parsed == truncate_event(event)


def test_emit_creates_logs_directory(tmp_path):
    event = _make_event(input_summary="dir test")
    assert not (tmp_path / ".maestro").exists()
    emit_event(event, tmp_path)
    assert (tmp_path / ".maestro" / "logs").is_dir()


def test_emit_truncates_oversize_input(tmp_path):
    event = _make_event(input_summary="x" * 10_000)
    emit_event(event, tmp_path)

    log_file = tmp_path / ".maestro" / "logs" / "dispatch.jsonl"
    line = log_file.read_bytes().split(b"\n")[0]
    assert len(line) <= 4096

    parsed = DISPATCH_EVENT_ADAPTER.validate_json(line)
    # T3.1's truncation marker is `…<truncated N→C bytes>…`.
    assert "<truncated " in parsed.input_summary


def test_emit_oserror_writes_stderr_returns_none(tmp_path, capsys, monkeypatch):
    def raise_oserror(*args, **kwargs):
        raise OSError("disk full")
    monkeypatch.setattr("maestro.dispatch_log.writer.os.write", raise_oserror)

    event = _make_event(request_id="err1", input_summary="write error test")
    result = emit_event(event, tmp_path)
    captured = capsys.readouterr()

    assert "maestro: dispatch log write failed" in captured.err
    assert result is None


def test_emit_oserror_on_mkdir_writes_stderr_returns_none(tmp_path, capsys, monkeypatch):
    def raise_mkdir(*args, **kwargs):
        raise OSError("permission denied")
    monkeypatch.setattr("pathlib.Path.mkdir", raise_mkdir)

    event = _make_event(request_id="err2", input_summary="mkdir error test")
    result = emit_event(event, tmp_path)
    captured = capsys.readouterr()

    assert "maestro: dispatch log mkdir failed" in captured.err
    assert result is None


def test_rotate_at_5mb_threshold(tmp_path):
    log_dir = tmp_path / ".maestro" / "logs"
    log_dir.mkdir(parents=True)
    log_file = log_dir / "dispatch.jsonl"
    log_file.write_bytes(b"0" * (5 * 1024 * 1024 + 1))

    event = _make_event(request_id="rotate-test", input_summary="rotation trigger")
    emit_event(event, tmp_path)

    archives = list(log_dir.glob("dispatch.*.jsonl"))
    # The glob matches both archive and live file; subtract the live one.
    archives = [a for a in archives if a.name != "dispatch.jsonl"]
    assert len(archives) == 1
    archive = archives[0]
    assert archive.stat().st_size == 5 * 1024 * 1024 + 1

    lines = [l for l in log_file.read_bytes().split(b"\n") if l]
    assert len(lines) == 1
    parsed = DISPATCH_EVENT_ADAPTER.validate_json(lines[0])
    assert parsed.request_id == "rotate-test"


def test_rotate_does_not_trigger_at_exactly_threshold(tmp_path):
    log_dir = tmp_path / ".maestro" / "logs"
    log_dir.mkdir(parents=True)
    log_file = log_dir / "dispatch.jsonl"
    log_file.write_bytes(b"1" * (5 * 1024 * 1024))

    event = _make_event(request_id="no-rotate", input_summary="just under")
    emit_event(event, tmp_path)

    archives = [a for a in log_dir.glob("dispatch.*.jsonl") if a.name != "dispatch.jsonl"]
    assert len(archives) == 0
    assert log_file.stat().st_size > 5 * 1024 * 1024


def test_two_concurrent_processes_dont_tear_lines(tmp_path):
    pythonpath = os.environ.get("PYTHONPATH", "")
    if pythonpath:
        pythonpath = f"{PROJECT_ROOT}{os.pathsep}{pythonpath}"
    else:
        pythonpath = str(PROJECT_ROOT)
    env = {**os.environ, "PYTHONPATH": pythonpath}

    child_script = (
        "import sys\n"
        f"sys.path.insert(0, {str(PROJECT_ROOT)!r})\n"
        "from pathlib import Path\n"
        "from datetime import datetime, timezone\n"
        "from maestro.dispatch_log.writer import emit_event\n"
        "from maestro.dispatch_log.events import DispatchStartEvent\n"
        "\n"
        "root = Path(sys.argv[1])\n"
        "role = sys.argv[2]\n"
        "for i in range(200):\n"
        "    ev = DispatchStartEvent(\n"
        "        event_version=1,\n"
        "        request_id=f'{role}-{i:03d}',\n"
        "        timestamp=datetime.now(timezone.utc),\n"
        "        role='coder',\n"
        "        model='deepseek-v4-pro',\n"
        "        member='alice',\n"
        "        input_summary=f'role_{role}_item_{i:04d}',\n"
        "    )\n"
        "    emit_event(ev, root)\n"
    )

    proc1 = _REAL_SUBPROCESS_RUN(
        [sys.executable, "-c", child_script, str(tmp_path), "A"],
        capture_output=True, text=True, timeout=15, env=env,
    )
    proc2 = _REAL_SUBPROCESS_RUN(
        [sys.executable, "-c", child_script, str(tmp_path), "B"],
        capture_output=True, text=True, timeout=15, env=env,
    )

    assert proc1.returncode == 0, proc1.stderr
    assert proc2.returncode == 0, proc2.stderr

    log_file = tmp_path / ".maestro" / "logs" / "dispatch.jsonl"
    lines = log_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 400

    role_a = 0
    role_b = 0
    for raw in lines:
        ev = DISPATCH_EVENT_ADAPTER.validate_json(raw)
        if "role_A_" in ev.input_summary:
            role_a += 1
        elif "role_B_" in ev.input_summary:
            role_b += 1
    assert role_a == 200
    assert role_b == 200
