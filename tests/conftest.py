"""Test fixtures shared across the suite.

Autouse: every test runs with MAESTRO_DISPATCH_LOG redirected to a temp
file so worker tests don't pollute the real dispatch log. Per-test
MAESTRO_CURRENT_TASK / MAESTRO_CURRENT_ISSUE are also cleared so each
test sets them explicitly when it cares.
"""

import pytest


@pytest.fixture(autouse=True)
def isolate_dispatch_log(tmp_path, monkeypatch):
    """Redirect telemetry writes to a per-test tmp file."""
    log = tmp_path / "dispatch-log.jsonl"
    monkeypatch.setenv("MAESTRO_DISPATCH_LOG", str(log))
    monkeypatch.delenv("MAESTRO_CURRENT_TASK", raising=False)
    monkeypatch.delenv("MAESTRO_CURRENT_ISSUE", raising=False)
    return log
