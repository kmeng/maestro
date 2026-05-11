"""tests/test_dispatcher.py — unit tests for async dispatcher.run()."""

import textwrap

import pytest

from maestro.dispatch_log.events import (
    DispatchEndEvent,
    DispatchFailedEvent,
    DispatchFallbackConfigAbsentEvent,
    DispatchRefusedConfigInvalidEvent,
    DispatchStartEvent,
)
from maestro.dispatch_log.reader import scan_log
from maestro.dispatcher import run
from maestro.team.io import save_team_config
from maestro.team.models import RoleEntry, TeamConfig


def _make_valid_config() -> TeamConfig:
    return TeamConfig(
        schema_version=1,
        roles={
            "coder": RoleEntry(member="alice", model="deepseek-v4-pro"),
            "librarian": RoleEntry(member="bob", model="deepseek-v4-flash"),
            "reviewer": RoleEntry(member="carol", model="deepseek-v4-pro"),
            "scribe": RoleEntry(member="dave", model="deepseek-v4-flash"),
        },
    )


@pytest.mark.asyncio
async def test_happy_path_with_valid_config(tmp_path, monkeypatch):
    save_team_config(tmp_path, _make_valid_config())
    monkeypatch.setattr("maestro.dispatcher.Path.cwd", lambda: tmp_path)

    async def executor(model):
        return f"output from {model}"

    result = await run("coder", "test input", executor)
    assert result == "output from deepseek-v4-pro"

    events = scan_log(tmp_path / ".maestro" / "logs" / "dispatch.jsonl")
    assert len(events) == 2
    start, end = events
    assert isinstance(start, DispatchStartEvent)
    assert start.role == "coder"
    assert start.model == "deepseek-v4-pro"
    assert start.input_summary == "test input"
    assert isinstance(end, DispatchEndEvent)
    assert end.output_summary == "output from deepseek-v4-pro"
    assert start.request_id == end.request_id


@pytest.mark.asyncio
async def test_absent_config_emits_fallback_then_start_end(tmp_path, monkeypatch):
    monkeypatch.setattr("maestro.dispatcher.Path.cwd", lambda: tmp_path)

    async def executor(m):
        return "ok"

    result = await run("coder", "input", executor)
    assert result == "ok"

    events = scan_log(tmp_path / ".maestro" / "logs" / "dispatch.jsonl")
    assert len(events) == 3
    fallback, start, end = events
    assert isinstance(fallback, DispatchFallbackConfigAbsentEvent)
    assert fallback.role == "coder"
    assert fallback.fallback_model == "deepseek-v4-pro"
    assert isinstance(start, DispatchStartEvent)
    assert start.model == "deepseek-v4-pro"
    assert isinstance(end, DispatchEndEvent)
    assert start.request_id == fallback.request_id == end.request_id


@pytest.mark.asyncio
async def test_invalid_config_refuses_and_returns_error_string(tmp_path, monkeypatch):
    broken_yaml = textwrap.dedent("""\
        schema_version: 1
        roles:
          coder:
            member: alice
            model: "BAD CASE"
          librarian:
            member: bob
            model: deepseek-v4-flash
          reviewer:
            member: carol
            model: deepseek-v4-pro
          scribe:
            member: dave
            model: deepseek-v4-flash
    """)
    (tmp_path / ".maestro").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".maestro" / "team.yaml").write_text(broken_yaml)
    monkeypatch.setattr("maestro.dispatcher.Path.cwd", lambda: tmp_path)

    called = []
    async def executor(m):
        called.append(m)
        return "should not run"

    result = await run("coder", "input", executor)

    assert called == []
    assert result.startswith("team.yaml at .maestro/team.yaml is invalid: ")
    assert "roles.coder.model" in result

    events = scan_log(tmp_path / ".maestro" / "logs" / "dispatch.jsonl")
    assert len(events) == 1
    refused = events[0]
    assert isinstance(refused, DispatchRefusedConfigInvalidEvent)
    assert refused.validation_error_field == "roles.coder"


@pytest.mark.asyncio
async def test_executor_exception_emits_failed_then_reraises(tmp_path, monkeypatch):
    save_team_config(tmp_path, _make_valid_config())
    monkeypatch.setattr("maestro.dispatcher.Path.cwd", lambda: tmp_path)

    async def boom(model):
        raise ValueError("kaboom")

    with pytest.raises(ValueError, match="kaboom"):
        await run("coder", "input", boom)

    events = scan_log(tmp_path / ".maestro" / "logs" / "dispatch.jsonl")
    assert len(events) == 2
    start, failed = events
    assert isinstance(start, DispatchStartEvent)
    assert isinstance(failed, DispatchFailedEvent)
    assert failed.error_kind == "ValueError"
    assert failed.error_message == "kaboom"
    assert start.request_id == failed.request_id


@pytest.mark.asyncio
async def test_emit_event_failure_does_not_break_dispatch(tmp_path, monkeypatch, capsys):
    save_team_config(tmp_path, _make_valid_config())
    monkeypatch.setattr("maestro.dispatcher.Path.cwd", lambda: tmp_path)

    def _write_raise(*args, **kwargs):
        raise OSError("disk full")
    monkeypatch.setattr("maestro.dispatch_log.writer.os.write", _write_raise)

    async def executor(m):
        return "output ok"

    result = await run("coder", "input", executor)
    assert result == "output ok"

    captured = capsys.readouterr()
    assert "maestro: dispatch log write failed" in captured.err

    events = scan_log(tmp_path / ".maestro" / "logs" / "dispatch.jsonl")
    assert len(events) == 0
