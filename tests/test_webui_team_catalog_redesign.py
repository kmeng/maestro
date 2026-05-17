from pathlib import Path
import textwrap

import pytest
from fastapi.testclient import TestClient

from maestro.webui import app
from maestro.webui import team_api


@pytest.fixture
def team_root(tmp_path, monkeypatch):
    """Patch the project root so team.yaml lives in tmp_path/.maestro/."""
    monkeypatch.setattr(team_api, "_project_root", lambda: tmp_path)
    maestro_dir = tmp_path / ".maestro"
    maestro_dir.mkdir()
    return tmp_path


def _write_valid_team(root: Path) -> None:
    (root / ".maestro" / "team.yaml").write_text(textwrap.dedent("""\
        schema_version: 1
        roles:
          coder:
            member: cody
            model: deepseek-coder
          librarian:
            member: lily
            model: deepseek-coder
          reviewer:
            member: rae
            model: haiku-4-5
          scribe:
            member: sage
            model: haiku-4-5
    """))


def test_team_catalog_extends_base(team_root):
    _write_valid_team(team_root)
    client = TestClient(app)
    r = client.get("/team")
    assert r.status_code == 200
    body = r.text
    assert 'class="sidebar"' in body
    assert 'class="page-h1">团队</h1>' in body
    assert 'class="data-table"' in body
    assert "<style>" not in body
    for member in ("cody", "lily", "rae", "sage"):
        assert member in body


def test_team_catalog_missing_state(team_root):
    client = TestClient(app)
    r = client.get("/team")
    assert r.status_code == 200
    body = r.text
    assert "empty-state" in body
    assert "立即组建" in body
    assert 'href="/wizard"' in body
