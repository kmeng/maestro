"""Tests for T6.2 structured JSONL dispatch telemetry.

Coverage: row schema, env-var modes (default / disabled / redirected /
parent-dir creation / unwritable), task-id env vars, error path,
row_id format, per-(task,tool) sequence independence.

Mocks deepseek the same way `tests/test_workers.py` does:
`monkeypatch.setattr(server.deepseek.chat.completions, "create", mock)`,
then dispatches via `asyncio.run(server._foo_impl({...}))`.
"""

import asyncio
import importlib.util
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest


_REPO_ROOT = Path(__file__).resolve().parent.parent
_BOOTSTRAP = _REPO_ROOT / "bootstrap" / "maestro_server.py"


@pytest.fixture(scope="function")
def server():
    """Load a fresh maestro_server module per test so _DISPATCH_SEQ is reset."""
    spec = importlib.util.spec_from_file_location("maestro_server", _BOOTSTRAP)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _mock_resp(content: str, total_tokens: int = 30):
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = MagicMock(
        prompt_tokens=10, completion_tokens=20, total_tokens=total_tokens
    )
    return resp


def _valid_librarian_json():
    return json.dumps({
        "hard_constraints": [],
        "summary": "ok",
        "recommend_full_read": [],
        "concerns": [],
    })


def _valid_reviewer_json():
    return json.dumps({
        "verdict": "pass",
        "findings": [],
        "missed_requirements": [],
        "concerns": [],
    })


def _valid_scribe_json():
    return json.dumps({
        "commit_message": "feat: x",
        "pr_title": "x",
        "pr_body": "x",
        "concerns": [],
    })


def _read_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


# ============================================================
# Row schema + happy path
# ============================================================


def test_emit_writes_one_row_per_successful_dispatch(server, monkeypatch, tmp_path):
    """A successful coder dispatch produces exactly one schema-valid row."""
    mock = AsyncMock(return_value=_mock_resp("def f(): pass", total_tokens=30))
    monkeypatch.setattr(server.deepseek.chat.completions, "create", mock)

    asyncio.run(server._coder_impl({"spec": "trivial", "language": "python"}))

    rows = _read_rows(tmp_path / "dispatch-log.jsonl")
    assert len(rows) == 1
    row = rows[0]
    assert row["tool"] == "coder"
    assert row["model"] == server.MODEL_PRO
    assert row["model_provider"] == "deepseek"
    assert row["total_tokens"] == 30
    assert row["prompt_tokens"] == 10
    assert row["completion_tokens"] == 20
    assert row["error"] is None
    assert row["schema_version"] == 1
    assert row["is_estimate"] is False
    assert row["est_method"] is None
    assert row["supersedes"] is None
    assert isinstance(row["started_at"], str) and row["started_at"].endswith("Z")
    assert "row_id" in row


# ============================================================
# Task-id env var sourcing
# ============================================================


def test_emit_records_task_id_when_env_set(server, monkeypatch, tmp_path, recwarn):
    monkeypatch.setenv("MAESTRO_CURRENT_TASK", "T6.2")
    monkeypatch.setenv("MAESTRO_CURRENT_ISSUE", "58")
    mock = AsyncMock(return_value=_mock_resp(_valid_librarian_json(), total_tokens=5))
    monkeypatch.setattr(server.deepseek.chat.completions, "create", mock)

    asyncio.run(server._librarian_impl({"document_text": "doc", "query": "q"}))

    row = _read_rows(tmp_path / "dispatch-log.jsonl")[0]
    assert row["task_id"] == "T6.2"
    assert row["issue_number"] == 58

    # T6.8 added: env-var path now warns deprecation (one-shot per process).
    deps = [w for w in recwarn.list if issubclass(w.category, DeprecationWarning)]
    assert len(deps) == 1
    assert "MAESTRO_CURRENT_TASK" in str(deps[0].message)


def test_emit_records_null_task_when_env_unset(server, monkeypatch, tmp_path):
    """Conftest deletes MAESTRO_CURRENT_TASK / ISSUE; null fields expected."""
    mock = AsyncMock(return_value=_mock_resp(_valid_reviewer_json(), total_tokens=1))
    monkeypatch.setattr(server.deepseek.chat.completions, "create", mock)

    asyncio.run(server._reviewer_impl({
        "spec": "s", "code": "def f(): pass", "language": "python",
    }))

    row = _read_rows(tmp_path / "dispatch-log.jsonl")[0]
    assert row["task_id"] is None
    assert row["issue_number"] is None


def test_emit_handles_invalid_issue_number_env(server, monkeypatch, tmp_path):
    """Non-integer ISSUE env var degrades to null, not crash."""
    monkeypatch.setenv("MAESTRO_CURRENT_ISSUE", "not-a-number")
    mock = AsyncMock(return_value=_mock_resp(_valid_librarian_json(), total_tokens=1))
    monkeypatch.setattr(server.deepseek.chat.completions, "create", mock)

    asyncio.run(server._librarian_impl({"document_text": "d", "query": "q"}))

    row = _read_rows(tmp_path / "dispatch-log.jsonl")[0]
    assert row["issue_number"] is None


# ============================================================
# MAESTRO_DISPATCH_LOG modes
# ============================================================


def test_disabled_when_env_var_empty(server, monkeypatch, tmp_path):
    """Empty string disables writes; dispatch still works."""
    monkeypatch.setenv("MAESTRO_DISPATCH_LOG", "")
    mock = AsyncMock(return_value=_mock_resp(_valid_scribe_json(), total_tokens=1))
    monkeypatch.setattr(server.deepseek.chat.completions, "create", mock)

    result = asyncio.run(server._scribe_impl({
        "diff": "+x",
        "purpose": "Issue #1 (t): b",
    }))
    assert len(result) == 1
    assert not (tmp_path / "dispatch-log.jsonl").exists()


def test_redirected_when_env_var_set_to_path(server, monkeypatch, tmp_path):
    """Conftest already redirects to tmp_path; verify the row lands there."""
    mock = AsyncMock(return_value=_mock_resp("c", total_tokens=1))
    monkeypatch.setattr(server.deepseek.chat.completions, "create", mock)

    asyncio.run(server._coder_impl({"spec": "x", "language": "python"}))

    rows = _read_rows(tmp_path / "dispatch-log.jsonl")
    assert len(rows) == 1


def test_creates_parent_dir_when_missing(server, monkeypatch, tmp_path):
    """Nested log path's parent dirs are created on first write."""
    log_path = tmp_path / "sub" / "deep" / "log.jsonl"
    monkeypatch.setenv("MAESTRO_DISPATCH_LOG", str(log_path))
    mock = AsyncMock(return_value=_mock_resp(_valid_librarian_json(), total_tokens=1))
    monkeypatch.setattr(server.deepseek.chat.completions, "create", mock)

    asyncio.run(server._librarian_impl({"document_text": "d", "query": "q"}))

    assert log_path.parent.is_dir()
    assert log_path.is_file()


def test_unwritable_path_does_not_break_dispatch(server, monkeypatch):
    """A guaranteed-unwritable log path must not propagate errors."""
    monkeypatch.setenv("MAESTRO_DISPATCH_LOG", "/dev/null/cant-write/here.jsonl")
    mock = AsyncMock(return_value=_mock_resp("c", total_tokens=1))
    monkeypatch.setattr(server.deepseek.chat.completions, "create", mock)

    result = asyncio.run(server._coder_impl({"spec": "x", "language": "python"}))
    assert len(result) == 1
    assert result[0].text  # banner + body still produced


# ============================================================
# Error path
# ============================================================


def test_error_path_emits_row_with_error_field(server, monkeypatch, tmp_path):
    """Coder dispatch where the API raises records error + null usage."""
    mock = AsyncMock(side_effect=RuntimeError("boom"))
    monkeypatch.setattr(server.deepseek.chat.completions, "create", mock)

    asyncio.run(server._coder_impl({"spec": "x", "language": "python"}))

    row = _read_rows(tmp_path / "dispatch-log.jsonl")[0]
    assert row["error"] is not None
    assert "boom" in row["error"]
    assert row["total_tokens"] is None


# ============================================================
# row_id format + sequence behaviour
# ============================================================


def test_row_id_format_includes_prefix_task_tool_seq(server, monkeypatch, tmp_path):
    """Two coder dispatches under the same task get seq 1 and 2."""
    monkeypatch.setenv("MAESTRO_CURRENT_TASK", "T0.4")
    mock = AsyncMock(return_value=_mock_resp("c", total_tokens=1))
    monkeypatch.setattr(server.deepseek.chat.completions, "create", mock)

    asyncio.run(server._coder_impl({"spec": "x", "language": "python"}))
    asyncio.run(server._coder_impl({"spec": "y", "language": "python"}))

    rows = _read_rows(tmp_path / "dispatch-log.jsonl")
    assert len(rows) == 2
    assert rows[0]["row_id"].endswith("T0.4-coder-1")
    assert rows[1]["row_id"].endswith("T0.4-coder-2")


def test_seq_per_task_tool_combination_independent(server, monkeypatch, tmp_path):
    """Coder seq and librarian seq are independent counters under same task."""
    monkeypatch.setenv("MAESTRO_CURRENT_TASK", "T0.4")
    mock = AsyncMock(return_value=_mock_resp(_valid_librarian_json(), total_tokens=1))
    monkeypatch.setattr(server.deepseek.chat.completions, "create", mock)
    asyncio.run(server._librarian_impl({"document_text": "d", "query": "q"}))

    mock = AsyncMock(return_value=_mock_resp("c", total_tokens=1))
    monkeypatch.setattr(server.deepseek.chat.completions, "create", mock)
    asyncio.run(server._coder_impl({"spec": "x", "language": "python"}))

    rows = _read_rows(tmp_path / "dispatch-log.jsonl")
    assert len(rows) == 2
    # Both should have seq=1 because (task,tool) keys differ
    assert rows[0]["row_id"].endswith("T0.4-librarian-1")
    assert rows[1]["row_id"].endswith("T0.4-coder-1")


# ============================================================
# Attribution precedence chain (T6.8 / ADR-0011)
# ============================================================


def test_emit_uses_explicit_param(server, monkeypatch, tmp_path):
    """Explicit task_id/issue_number on dispatch wins over env var."""
    monkeypatch.setenv("MAESTRO_CURRENT_TASK", "T_ENV")
    monkeypatch.setenv("MAESTRO_CURRENT_ISSUE", "999")
    mock = AsyncMock(return_value=_mock_resp(_valid_librarian_json(), total_tokens=5))
    monkeypatch.setattr(server.deepseek.chat.completions, "create", mock)

    asyncio.run(server._librarian_impl({
        "query": "q",
        "document_text": "d",
        "task_id": "T6.8",
        "issue_number": 64,
    }))

    row = _read_rows(tmp_path / "dispatch-log.jsonl")[0]
    assert row["task_id"] == "T6.8"
    assert row["issue_number"] == 64


def test_emit_partial_param_no_backfill(server, monkeypatch, tmp_path):
    """Passing only task_id does NOT backfill issue_number from env."""
    monkeypatch.setenv("MAESTRO_CURRENT_ISSUE", "999")
    mock = AsyncMock(return_value=_mock_resp(_valid_librarian_json(), total_tokens=1))
    monkeypatch.setattr(server.deepseek.chat.completions, "create", mock)

    asyncio.run(server._librarian_impl({
        "query": "q",
        "document_text": "d",
        "task_id": "T6.8",
    }))

    row = _read_rows(tmp_path / "dispatch-log.jsonl")[0]
    assert row["task_id"] == "T6.8"
    assert row["issue_number"] is None  # NOT 999


def test_emit_env_warns_deprecation(server, monkeypatch, tmp_path, recwarn):
    """First env-var-driven dispatch emits DeprecationWarning."""
    monkeypatch.setenv("MAESTRO_CURRENT_TASK", "T_ENV")
    mock = AsyncMock(return_value=_mock_resp(_valid_librarian_json(), total_tokens=1))
    monkeypatch.setattr(server.deepseek.chat.completions, "create", mock)

    asyncio.run(server._librarian_impl({"query": "q", "document_text": "d"}))

    deps = [w for w in recwarn.list if issubclass(w.category, DeprecationWarning)]
    assert len(deps) == 1
    assert "MAESTRO_CURRENT_TASK" in str(deps[0].message)


def test_emit_env_warning_one_shot(server, monkeypatch, tmp_path, recwarn):
    """Subsequent env-driven dispatches in the same process do not warn."""
    monkeypatch.setenv("MAESTRO_CURRENT_TASK", "T_ENV")
    mock = AsyncMock(return_value=_mock_resp(_valid_librarian_json(), total_tokens=1))
    monkeypatch.setattr(server.deepseek.chat.completions, "create", mock)

    for _ in range(3):
        asyncio.run(server._librarian_impl({"query": "q", "document_text": "d"}))

    deps = [w for w in recwarn.list if issubclass(w.category, DeprecationWarning)]
    assert len(deps) == 1


def test_emit_branch_inference(server, monkeypatch, tmp_path):
    """When no param + no env, a branch matching the convention infers issue_number."""
    fake = MagicMock(returncode=0, stdout="feature/64-retire-begin-task\n")
    monkeypatch.setattr(server.subprocess, "run", lambda *a, **kw: fake)

    mock = AsyncMock(return_value=_mock_resp(_valid_librarian_json(), total_tokens=1))
    monkeypatch.setattr(server.deepseek.chat.completions, "create", mock)

    asyncio.run(server._librarian_impl({"query": "q", "document_text": "d"}))

    row = _read_rows(tmp_path / "dispatch-log.jsonl")[0]
    assert row["task_id"] is None
    assert row["issue_number"] == 64


def test_emit_branch_inference_unmatched(server, monkeypatch, tmp_path):
    """A branch like wip/64-foo does NOT match; row is unattributed."""
    fake = MagicMock(returncode=0, stdout="wip/64-foo\n")
    monkeypatch.setattr(server.subprocess, "run", lambda *a, **kw: fake)

    mock = AsyncMock(return_value=_mock_resp(_valid_librarian_json(), total_tokens=1))
    monkeypatch.setattr(server.deepseek.chat.completions, "create", mock)

    asyncio.run(server._librarian_impl({"query": "q", "document_text": "d"}))

    row = _read_rows(tmp_path / "dispatch-log.jsonl")[0]
    assert row["task_id"] is None
    assert row["issue_number"] is None


def test_emit_unattributed_when_subprocess_fails(server, monkeypatch, tmp_path):
    """Subprocess failure (no git, OSError) falls through to unattributed."""
    def _raise(*a, **kw):
        raise OSError("no git binary")
    monkeypatch.setattr(server.subprocess, "run", _raise)

    mock = AsyncMock(return_value=_mock_resp(_valid_librarian_json(), total_tokens=1))
    monkeypatch.setattr(server.deepseek.chat.completions, "create", mock)

    asyncio.run(server._librarian_impl({"query": "q", "document_text": "d"}))

    row = _read_rows(tmp_path / "dispatch-log.jsonl")[0]
    assert row["task_id"] is None
    assert row["issue_number"] is None


def test_branch_re_patterns(server):
    """Regex matches feature/fix/refactor/docs only; rejects wip and missing N."""
    # Match
    assert server._BRANCH_RE.match("feature/64-x").group(1) == "64"
    assert server._BRANCH_RE.match("fix/123-y").group(1) == "123"
    assert server._BRANCH_RE.match("refactor/9-z").group(1) == "9"
    assert server._BRANCH_RE.match("docs/1-w").group(1) == "1"
    # No match
    assert server._BRANCH_RE.match("wip/64-x") is None
    assert server._BRANCH_RE.match("feature/abc") is None
    assert server._BRANCH_RE.match("main") is None
    assert server._BRANCH_RE.match("v0.0.3") is None


def test_scribe_attribution_uses_optional_issue_number_and_task_id(server, monkeypatch, tmp_path):
    """T8.8: issue_number is now optional telemetry; passing it still attributes."""
    mock = AsyncMock(return_value=_mock_resp(_valid_scribe_json(), total_tokens=1))
    monkeypatch.setattr(server.deepseek.chat.completions, "create", mock)

    asyncio.run(server._scribe_impl({
        "diff": "+x",
        "purpose": "Issue #64 (t): b",
        "issue_number": 64,
        "task_id": "T6.8",
    }))

    row = _read_rows(tmp_path / "dispatch-log.jsonl")[0]
    assert row["task_id"] == "T6.8"
    assert row["issue_number"] == 64
