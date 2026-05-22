from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from maestro.webui import app
from maestro.registry.projects import ProjectEntry


def test_scaffold_picker_extends_base():
    client = TestClient(app)
    r = client.get("/scaffold")
    assert r.status_code == 200
    body = r.text
    assert 'class="sidebar"' in body
    assert 'class="page-h1">脚手架</h1>' in body
    assert 'name="path"' in body
    assert 'name="mode"' in body
    assert "<style>" not in body  # no inline page-level style block in picker


def test_scaffold_lists_applied_projects(monkeypatch):
    entries = [
        ProjectEntry(
            path=Path("/tmp/proj-alpha"),
            last_opened_at=datetime(2026, 5, 8, 14, 23, tzinfo=timezone.utc),
        ),
        ProjectEntry(
            path=Path("/tmp/proj-beta"),
            last_opened_at=datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc),
        ),
    ]
    monkeypatch.setattr("maestro.webui.scaffold_view.read_registry", lambda: entries)
    body = TestClient(app).get("/scaffold").text
    assert "/tmp/proj-alpha" in body
    assert "/tmp/proj-beta" in body
    # take_over plan link present; path is urlencoded → slashes become %2F.
    assert "mode=take_over" in body
    assert "%2Ftmp%2Fproj-alpha" in body


def test_scaffold_empty_registry_shows_placeholder(monkeypatch):
    monkeypatch.setattr("maestro.webui.scaffold_view.read_registry", lambda: [])
    body = TestClient(app).get("/scaffold").text
    assert "还没有在任何项目上应用过 Maestro" in body
    assert 'name="path"' in body  # form still present
