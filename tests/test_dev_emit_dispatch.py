"""Tests for scripts/dev_emit_dispatch.py — stub event emission."""

import importlib.util
import json
from pathlib import Path

import pytest


@pytest.fixture
def emit_module():
    """Load scripts/dev_emit_dispatch.py as a module (it's not on sys.path normally)."""
    repo_root = Path(__file__).resolve().parent.parent
    script_path = repo_root / "scripts" / "dev_emit_dispatch.py"
    spec = importlib.util.spec_from_file_location("dev_emit_dispatch", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_first_run_creates_logs_dir_and_file(tmp_path, emit_module):
    """Call main once and assert the log file is created."""
    emit_module.main(["--project", str(tmp_path)])
    log_file = tmp_path / ".maestro" / "logs" / "dispatch.jsonl"
    assert log_file.exists()


def test_each_run_appends_one_line(tmp_path, emit_module):
    """Call main twice; expect exactly 2 non-empty lines."""
    emit_module.main(["--project", str(tmp_path)])
    emit_module.main(["--project", str(tmp_path)])
    log_file = tmp_path / ".maestro" / "logs" / "dispatch.jsonl"
    lines = log_file.read_text(encoding="utf-8").splitlines()
    non_empty = [line for line in lines if line.strip()]
    assert len(non_empty) == 2


def test_event_is_valid_json_with_required_fields(tmp_path, emit_module):
    """Call main once; the written line is valid JSON and contains required keys."""
    emit_module.main(["--project", str(tmp_path)])
    log_file = tmp_path / ".maestro" / "logs" / "dispatch.jsonl"
    content = log_file.read_text(encoding="utf-8").strip()
    event = json.loads(content)
    assert set(event) >= {"ts", "outcome", "tool", "note"}
    assert event["outcome"] == "success"


def test_failure_flag_records_failure_outcome(tmp_path, emit_module):
    """Call main with --failure; outcome must be 'failure'."""
    emit_module.main(["--project", str(tmp_path), "--failure"])
    log_file = tmp_path / ".maestro" / "logs" / "dispatch.jsonl"
    event = json.loads(log_file.read_text(encoding="utf-8").strip())
    assert event["outcome"] == "failure"


def test_invalid_project_path_exits_nonzero(tmp_path, emit_module):
    """When the project directory does not exist, main returns nonzero."""
    ret = emit_module.main(["--project", str(tmp_path / "does-not-exist")])
    assert ret != 0


def test_mutually_exclusive_flags_rejected(tmp_path, emit_module):
    """Providing both --success and --failure raises SystemExit (argparse conflict)."""
    with pytest.raises(SystemExit) as exc_info:
        emit_module.main(["--project", str(tmp_path), "--success", "--failure"])
    assert exc_info.value.code != 0
