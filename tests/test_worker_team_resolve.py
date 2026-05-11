"""Integration tests for T1.6 — worker handlers reading team.yaml.

Covers:
- `_emit_team_event` helper writes to logs/team_events.jsonl best-effort
- `_resolve_role_or_refuse` helper returns model string vs refuse list
- Each of the 4 worker handlers (coder, librarian, reviewer, scribe)
  short-circuits with a refusal response when team.yaml is invalid
  (without calling the DeepSeek API)

The unit-level resolver logic (3 states × 4 roles) is covered by
tests/test_team_resolve.py. This module focuses on the bootstrap-server
integration points.
"""

import asyncio
import importlib.util
import json
from pathlib import Path

import pytest

from maestro.team import (
    DEFAULT_MODELS,
    RoleEntry,
    TeamConfig,
    save_team_config,
)


_REPO_ROOT = Path(__file__).resolve().parent.parent
_BOOTSTRAP = _REPO_ROOT / "bootstrap" / "maestro_server.py"


@pytest.fixture(scope="module")
def server():
    spec = importlib.util.spec_from_file_location("maestro_server_t16", _BOOTSTRAP)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _save_valid_config(project_root: Path) -> None:
    """Seed a valid team.yaml under project_root."""
    save_team_config(
        project_root,
        TeamConfig(
            schema_version=1,
            roles={
                "coder": RoleEntry(member="Cody", model=DEFAULT_MODELS["coder"]),
                "librarian": RoleEntry(member="Lily", model=DEFAULT_MODELS["librarian"]),
                "reviewer": RoleEntry(member="Rae", model=DEFAULT_MODELS["reviewer"]),
                "scribe": RoleEntry(member="Sage", model=DEFAULT_MODELS["scribe"]),
            },
        ),
    )


def _write_invalid_yaml(project_root: Path) -> None:
    """Seed a malformed team.yaml under project_root."""
    dot_maestro = project_root / ".maestro"
    dot_maestro.mkdir(parents=True, exist_ok=True)
    (dot_maestro / "team.yaml").write_text(": : :")


# ============================================================
# _emit_team_event
# ============================================================


def test_emit_team_event_writes_to_log_dir(server, monkeypatch, tmp_path):
    """Best-effort emission lands in <LOG_DIR>/team_events.jsonl."""
    monkeypatch.setattr(server, "LOG_DIR", tmp_path)

    server._emit_team_event(
        {"type": "dispatch.fallback.config_absent", "role": "coder", "model": "test-model"}
    )

    log_file = tmp_path / "team_events.jsonl"
    assert log_file.is_file()
    line = log_file.read_text(encoding="utf-8").strip()
    payload = json.loads(line)
    assert payload["type"] == "dispatch.fallback.config_absent"
    assert payload["role"] == "coder"
    assert payload["model"] == "test-model"
    assert "ts" in payload  # helper adds a timestamp


def test_emit_team_event_swallows_io_failures(server, monkeypatch):
    """Emission must never fail the dispatch — I/O errors are swallowed."""
    # Point LOG_DIR at a path whose parent does not exist and cannot be
    # created (a file masquerading as a parent dir).
    monkeypatch.setattr(server, "LOG_DIR", Path("/proc/1/non_existent_subdir/blocked"))

    # Should not raise even though the path is unwritable.
    server._emit_team_event({"type": "dispatch.refused.config_invalid"})


# ============================================================
# _resolve_role_or_refuse
# ============================================================


def test_resolve_or_refuse_absent_returns_default_model(server, monkeypatch, tmp_path):
    """Absent team.yaml → returns DEFAULT_MODELS[role] string + emits fallback event."""
    monkeypatch.setattr(server, "_PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(server, "LOG_DIR", tmp_path / "logs")

    result = server._resolve_role_or_refuse("coder")

    assert isinstance(result, str)
    assert result == DEFAULT_MODELS["coder"]
    # Fallback event should have been emitted to the log.
    log_file = tmp_path / "logs" / "team_events.jsonl"
    assert log_file.is_file()
    payload = json.loads(log_file.read_text().strip())
    assert payload["type"] == "dispatch.fallback.config_absent"


def test_resolve_or_refuse_valid_returns_configured_model(server, monkeypatch, tmp_path):
    """Valid team.yaml → returns the configured model with no event emitted."""
    _save_valid_config(tmp_path)
    monkeypatch.setattr(server, "_PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(server, "LOG_DIR", tmp_path / "logs")

    result = server._resolve_role_or_refuse("librarian")

    assert isinstance(result, str)
    assert result == DEFAULT_MODELS["librarian"]
    # No event should have been emitted on the valid path.
    log_file = tmp_path / "logs" / "team_events.jsonl"
    assert not log_file.exists()


def test_resolve_or_refuse_invalid_returns_text_content_list(server, monkeypatch, tmp_path):
    """Invalid team.yaml → returns list[TextContent] (refusal) + emits refused event."""
    _write_invalid_yaml(tmp_path)
    monkeypatch.setattr(server, "_PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(server, "LOG_DIR", tmp_path / "logs")

    result = server._resolve_role_or_refuse("scribe")

    assert isinstance(result, list)
    assert len(result) == 1
    assert "team.yaml" in result[0].text
    assert "invalid" in result[0].text.lower()
    # Refused event should have been emitted.
    log_file = tmp_path / "logs" / "team_events.jsonl"
    payload = json.loads(log_file.read_text().strip())
    assert payload["type"] == "dispatch.refused.config_invalid"
    assert payload["role"] == "scribe"


# ============================================================
# Per-handler refusal smoke tests
# ============================================================


@pytest.mark.parametrize(
    "handler_name,arguments",
    [
        ("_coder_impl", {"spec": "do x", "language": "python"}),
        (
            "_librarian_impl",
            {"file_path": str(_REPO_ROOT / "README.md"), "query": "find x"},
        ),
        (
            "_reviewer_impl",
            {"spec": "spec text", "code": "code text", "language": "python"},
        ),
        (
            "_scribe_impl",
            {
                "diff": "some diff",
                "issue_number": 1,
                "issue_title": "t",
                "issue_body": "b",
                "convention": "c",
            },
        ),
    ],
)
def test_handler_refuses_when_team_yaml_invalid(
    server, monkeypatch, tmp_path, handler_name, arguments
):
    """Each worker handler short-circuits with refusal when team.yaml is invalid.

    Verifies the resolver-or-refuse hook is wired into each handler before
    any DeepSeek API call would happen. We do NOT mock the deepseek client
    here — if the early return weren't wired, the test would fail with a
    network error or model_api_error response.
    """
    _write_invalid_yaml(tmp_path)
    monkeypatch.setattr(server, "_PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(server, "LOG_DIR", tmp_path / "logs")
    # T3.5b: _coder_impl now resolves via dispatcher.run which uses Path.cwd().
    # T3.5c will move the other 3 impls to the same path. Patch both sources
    # so the test works regardless of refactor stage.
    monkeypatch.setattr("maestro.dispatcher.Path.cwd", lambda: tmp_path)

    handler = getattr(server, handler_name)
    result = asyncio.run(handler(arguments))

    assert isinstance(result, list)
    # The refusal text from the resolver should appear in the response.
    text = result[0].text
    assert "team.yaml" in text
    assert "invalid" in text.lower()
