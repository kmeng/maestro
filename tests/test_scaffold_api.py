"""Unit tests for the scaffolding HTTP API (T2.6)."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient

from maestro.scaffold.operations import PreflightCheck
from maestro.scaffold.templates import render_claude_md_standalone
from maestro.webui import app

# Captured at module import — BEFORE conftest.py's autouse fixture
# stubs subprocess.run for T6.8 attribution. Needed by _git_init_clean
# helper below. See feedback_conftest_subprocess_patch_trap.md.
_REAL_SUBPROCESS_RUN = subprocess.run


def _git_init_clean(repo: Path) -> None:
    """Initialize a clean git repo for take_over preflight to pass.

    Uses the captured-at-import subprocess.run to bypass the conftest
    autouse fixture that stubs subprocess.run globally.
    """
    _REAL_SUBPROCESS_RUN(
        ["git", "init"], cwd=str(repo), check=True, capture_output=True
    )
    _REAL_SUBPROCESS_RUN(
        ["git", "config", "user.email", "test@example.com"],
        cwd=str(repo), check=True, capture_output=True,
    )
    _REAL_SUBPROCESS_RUN(
        ["git", "config", "user.name", "Test"],
        cwd=str(repo), check=True, capture_output=True,
    )
    (repo / "seed").write_text("initial")
    _REAL_SUBPROCESS_RUN(
        ["git", "add", "seed"], cwd=str(repo), check=True, capture_output=True
    )
    _REAL_SUBPROCESS_RUN(
        ["git", "commit", "-m", "init"],
        cwd=str(repo), check=True, capture_output=True,
    )


def _stub_preflight_all_pass(monkeypatch) -> None:
    """Replace run_preflight inside scaffold_api with a 4-PASS stub.

    Tests that don't care about preflight specifics use this to keep
    the conftest subprocess stub from poisoning the real
    preflight.check_clean_tree (which subprocess-calls git).
    """
    monkeypatch.setattr(
        "maestro.webui.scaffold_api.run_preflight",
        lambda root, flow: tuple(
            PreflightCheck(name=n, passed=True, message="ok")
            for n in ("directory_exists", "git_state", "clean_tree", "no_existing_maestro")
        ),
    )


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


# -- Plan endpoint ---------------------------------------------------------

def test_plan_new_project_empty_dir(client, tmp_path, monkeypatch):
    """Empty dir + new_project mode → 200, all preflight pass, 4 CREATE rows."""
    _stub_preflight_all_pass(monkeypatch)
    resp = client.post(
        "/api/scaffold/plan", json={"path": str(tmp_path), "mode": "new_project"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["preflight"]) == 4
    assert all(c["passed"] for c in data["preflight"])
    assert len(data["rows"]) == 4
    assert all(row["op"] == "CREATE" for row in data["rows"])


def test_plan_take_over_clean_git_repo(client, tmp_path, monkeypatch):
    """Clean git repo + take_over → 200, all preflight pass, 2 CREATE rows."""
    _stub_preflight_all_pass(monkeypatch)
    resp = client.post(
        "/api/scaffold/plan", json={"path": str(tmp_path), "mode": "take_over"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert all(c["passed"] for c in data["preflight"])
    assert len(data["rows"]) == 2
    assert all(row["op"] == "CREATE" for row in data["rows"])


def test_plan_preflight_fails_on_nonexistent_dir(client, tmp_path, monkeypatch):
    """Non-existent path → 200 (not 4xx); directory_exists preflight fails."""
    # Use real preflight here — directory_exists doesn't need subprocess.
    # But we have to override the conftest subprocess stub for clean_tree.
    # Easiest: stub run_preflight with a "directory_exists fails" tuple.
    monkeypatch.setattr(
        "maestro.webui.scaffold_api.run_preflight",
        lambda root, flow: (
            PreflightCheck(name="directory_exists", passed=False, message="not a dir"),
            PreflightCheck(name="git_state", passed=True, message="skipped"),
            PreflightCheck(name="clean_tree", passed=True, message="skipped"),
            PreflightCheck(name="no_existing_maestro", passed=True, message="skipped"),
        ),
    )
    bad = tmp_path / "nope"
    resp = client.post(
        "/api/scaffold/plan", json={"path": str(bad), "mode": "new_project"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["preflight"][0]["name"] == "directory_exists"
    assert data["preflight"][0]["passed"] is False


def test_plan_returns_correct_op_for_existing_file(client, tmp_path, monkeypatch):
    """Pre-written CLAUDE.md with no maestro section → APPEND_DELIMITED."""
    _stub_preflight_all_pass(monkeypatch)
    (tmp_path / "CLAUDE.md").write_text("Some random user content\n")
    resp = client.post(
        "/api/scaffold/plan", json={"path": str(tmp_path), "mode": "take_over"}
    )
    assert resp.status_code == 200
    rows = resp.json()["rows"]
    claude = [r for r in rows if r["path"] == "CLAUDE.md"]
    assert len(claude) == 1
    assert claude[0]["op"] == "APPEND_DELIMITED"


def test_plan_response_includes_conflict_reason_when_applicable(client, tmp_path, monkeypatch):
    """CLAUDE.md with v=2 marker → CONFLICT, conflict_reason=delimiter_version_mismatch.

    Note: use render_claude_md_standalone(2) (which produces wrapped
    bytes with v=2 markers), NOT render_claude_md_section_body(2)
    (which returns the body only — section_version is currently
    informational on body, real version lives in the wrapper).
    """
    _stub_preflight_all_pass(monkeypatch)
    (tmp_path / "CLAUDE.md").write_bytes(render_claude_md_standalone(section_version=2))
    resp = client.post(
        "/api/scaffold/plan", json={"path": str(tmp_path), "mode": "take_over"}
    )
    assert resp.status_code == 200
    rows = resp.json()["rows"]
    claude = [r for r in rows if r["path"] == "CLAUDE.md"]
    assert len(claude) == 1
    assert claude[0]["op"] == "CONFLICT"
    assert claude[0]["conflict_reason"] == "delimiter_version_mismatch"


# -- Apply endpoint --------------------------------------------------------

def _stream_events(client, body: dict) -> list[tuple[str, dict]]:
    """Consume SSE stream → list of (event_type, data_dict)."""
    events: list[tuple[str, dict]] = []
    current_event: str | None = None
    with client.stream("POST", "/api/scaffold/apply", json=body) as resp:
        for line in resp.iter_lines():
            if line.startswith("event: "):
                current_event = line[7:]
            elif line.startswith("data: "):
                assert current_event is not None
                events.append((current_event, json.loads(line[6:])))
                current_event = None
    return events


def test_apply_streams_file_started_succeeded_complete_in_order(client, tmp_path, monkeypatch):
    """Happy path: stream contains file_started → file_succeeded → plan_complete (in order)."""
    _stub_preflight_all_pass(monkeypatch)
    body = {
        "path": str(tmp_path),
        "mode": "take_over",
        "accepted_paths": [".maestro/.gitignore", "CLAUDE.md"],
    }
    events = _stream_events(client, body)
    types = [e[0] for e in events]
    assert "file_started" in types
    assert "file_succeeded" in types
    assert "plan_complete" in types
    assert types[-1] == "plan_complete"
    # Strict per-row ordering: every file_started precedes its
    # corresponding file_succeeded/failed.
    seen_started = set()
    seen_terminal = set()
    for etype, data in events:
        if etype == "file_started":
            seen_started.add(data["path"])
        elif etype in ("file_succeeded", "file_failed"):
            assert data["path"] in seen_started, f"{data['path']} terminal before started"
            seen_terminal.add(data["path"])
    assert seen_started == seen_terminal  # every started got a terminal


def test_apply_registers_project_on_plan_complete(client, tmp_path, monkeypatch):
    """upsert_project called exactly once with the resolved project_root."""
    _stub_preflight_all_pass(monkeypatch)
    calls: list[Path] = []
    monkeypatch.setattr(
        "maestro.webui.scaffold_api.upsert_project",
        lambda p: calls.append(p),
    )
    body = {
        "path": str(tmp_path),
        "mode": "take_over",
        "accepted_paths": [".maestro/.gitignore", "CLAUDE.md"],
    }
    _stream_events(client, body)
    assert len(calls) == 1
    assert calls[0] == tmp_path.resolve()


def test_apply_registers_on_partial_failure_too(client, tmp_path, monkeypatch):
    """Even with file failures (CONFLICT), upsert_project still called."""
    _stub_preflight_all_pass(monkeypatch)
    # Pre-write CLAUDE.md with v=2 → engine will mark CONFLICT, apply will
    # emit FileFailed for it.
    (tmp_path / "CLAUDE.md").write_bytes(render_claude_md_standalone(section_version=2))
    calls: list[Path] = []
    monkeypatch.setattr(
        "maestro.webui.scaffold_api.upsert_project",
        lambda p: calls.append(p),
    )
    body = {
        "path": str(tmp_path),
        "mode": "take_over",
        "accepted_paths": ["CLAUDE.md"],
    }
    events = _stream_events(client, body)
    failed = [e for e in events if e[0] == "file_failed"]
    assert len(failed) >= 1
    assert events[-1][0] == "plan_complete"
    assert len(calls) == 1


def test_apply_rejects_on_preflight_failure(client, tmp_path, monkeypatch):
    """Failing preflight → single plan_rejected event; upsert NOT called."""
    monkeypatch.setattr(
        "maestro.webui.scaffold_api.run_preflight",
        lambda root, flow: (
            PreflightCheck(name="directory_exists", passed=True, message="ok"),
            PreflightCheck(name="git_state", passed=False, message="not a repo"),
            PreflightCheck(name="clean_tree", passed=True, message="ok"),
            PreflightCheck(name="no_existing_maestro", passed=True, message="ok"),
        ),
    )
    calls: list[Path] = []
    monkeypatch.setattr(
        "maestro.webui.scaffold_api.upsert_project",
        lambda p: calls.append(p),
    )
    body = {"path": str(tmp_path), "mode": "take_over", "accepted_paths": []}
    events = _stream_events(client, body)
    assert len(events) == 1
    assert events[0][0] == "plan_rejected"
    assert events[0][1]["reason"] == "preflight_failed"
    assert calls == []


def test_apply_filters_to_accepted_paths(client, tmp_path, monkeypatch):
    """accepted_paths subset → only those files processed."""
    _stub_preflight_all_pass(monkeypatch)
    body = {
        "path": str(tmp_path),
        "mode": "new_project",
        "accepted_paths": ["CLAUDE.md"],
    }
    events = _stream_events(client, body)
    paths_seen = {
        e[1]["path"] for e in events
        if e[0] in ("file_started", "file_succeeded", "file_failed")
    }
    assert paths_seen == {"CLAUDE.md"}


# -- Validation tests ------------------------------------------------------

def test_apply_with_empty_accepted_paths_does_not_register(client, tmp_path, monkeypatch):
    """Empty accepted_paths → no files processed → upsert_project NOT called.

    Reviewer-flagged concern (T2.6 review round 1): UI should block
    this case (design 14 D3 — Apply button disabled if all opt-out
    checkboxes unchecked) but the HTTP layer defends too. Registering
    a project that had zero apply operations is semantically odd.
    """
    _stub_preflight_all_pass(monkeypatch)
    calls: list[Path] = []
    monkeypatch.setattr(
        "maestro.webui.scaffold_api.upsert_project",
        lambda p: calls.append(p),
    )
    body = {
        "path": str(tmp_path),
        "mode": "take_over",
        "accepted_paths": [],  # user opted out of everything
    }
    events = _stream_events(client, body)
    # Stream still emits plan_complete (with 0/0) so the client knows
    # the request was processed.
    assert events[-1][0] == "plan_complete"
    assert events[-1][1] == {"succeeded": 0, "failed": 0}
    # But upsert was NOT called.
    assert calls == []


def test_plan_request_body_validation(client):
    resp = client.post("/api/scaffold/plan", json={"path": "/tmp"})  # no mode
    assert resp.status_code == 422


def test_apply_request_body_validation(client):
    resp = client.post(
        "/api/scaffold/apply", json={"mode": "take_over"}  # no path
    )
    assert resp.status_code == 422
