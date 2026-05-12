"""Test fixtures shared across the suite.

Autouse: every test runs with MAESTRO_DISPATCH_LOG redirected to a temp
file so worker tests don't pollute the real dispatch log. Per-test
MAESTRO_CURRENT_TASK / MAESTRO_CURRENT_ISSUE are also cleared so each
test sets them explicitly when it cares. Per T6.8 (ADR-0011): git
branch inference is disabled by default (subprocess returns no-git
behaviour) so attribution doesn't depend on the dev's current branch.
Tests that want branch inference monkeypatch `server.subprocess.run`
themselves.
"""

import subprocess

import pytest


@pytest.fixture(autouse=True)
def isolate_dispatch_log(tmp_path, monkeypatch):
    """Redirect telemetry writes to a per-test tmp file and isolate
    attribution sources (env vars cleared; git subprocess neutralised)."""
    log = tmp_path / "dispatch-log.jsonl"
    monkeypatch.setenv("MAESTRO_DISPATCH_LOG", str(log))
    monkeypatch.delenv("MAESTRO_CURRENT_TASK", raising=False)
    monkeypatch.delenv("MAESTRO_CURRENT_ISSUE", raising=False)
    # Default: branch inference returns None (no-git behaviour). Tests that
    # want branch inference override `server.subprocess.run` themselves.
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess(args=a, returncode=128, stdout="", stderr=""),
    )
    return log
