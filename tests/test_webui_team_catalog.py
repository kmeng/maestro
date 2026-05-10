"""Tests for the standing team catalog view (T1.5)."""

import pytest
from fastapi.testclient import TestClient

from maestro.team import (
    DEFAULT_MODELS,
    RoleEntry,
    TeamConfig,
    load_team_config,
    save_team_config,
)


def _valid_config() -> TeamConfig:
    return TeamConfig(
        schema_version=1,
        roles={
            "coder": RoleEntry(member="Cody", model=DEFAULT_MODELS["coder"]),
            "librarian": RoleEntry(member="Lily", model=DEFAULT_MODELS["librarian"]),
            "reviewer": RoleEntry(member="Rae", model=DEFAULT_MODELS["reviewer"]),
            "scribe": RoleEntry(member="Sage", model=DEFAULT_MODELS["scribe"]),
        },
    )


@pytest.fixture
def app(monkeypatch, tmp_path):
    monkeypatch.setattr("maestro.webui.team_api._project_root", lambda: tmp_path)
    from maestro.webui import app as configured_app

    return configured_app


@pytest.fixture
def client(app):
    return TestClient(app)


def test_get_renders_missing_banner_when_no_team_yaml(client):
    resp = client.get("/team")
    assert resp.status_code == 200
    assert "尚未组建团队" in resp.text
    assert 'href="/wizard"' in resp.text


def test_get_renders_invalid_banner_when_team_yaml_invalid(client, tmp_path):
    team_dir = tmp_path / ".maestro"
    team_dir.mkdir()
    (team_dir / "team.yaml").write_text(": : :", encoding="utf-8")
    resp = client.get("/team")
    assert resp.status_code == 200
    assert "team.yaml 配置无效" in resp.text


def test_get_renders_table_when_valid(client, tmp_path):
    save_team_config(tmp_path, _valid_config())
    resp = client.get("/team")
    assert resp.status_code == 200
    content = resp.text
    assert "Claude Code 主会话" in content
    for title in ["编码员", "图书管理员", "审阅员", "记录员"]:
        assert title in content
    for member in ["Cody", "Lily", "Rae", "Sage"]:
        assert member in content


def test_get_edit_returns_edit_partial(client, tmp_path):
    save_team_config(tmp_path, _valid_config())
    resp = client.get("/team/edit/coder")
    assert resp.status_code == 200
    assert '<input name="member"' in resp.text
    assert 'value="Cody"' in resp.text


def test_get_edit_unknown_role_404s(client):
    resp = client.get("/team/edit/architect")
    assert resp.status_code == 404


def test_post_edit_saves_and_returns_view_row(client, tmp_path):
    save_team_config(tmp_path, _valid_config())
    resp = client.post(
        "/team/edit/coder",
        data={"member": "NewCody", "model": "deepseek-v4-pro"},
    )
    assert resp.status_code == 200
    content = resp.text
    assert "NewCody" in content
    assert '<input name="member"' not in content
    config = load_team_config(tmp_path)
    assert config.roles["coder"].member == "NewCody"


def test_post_edit_invalid_value_returns_edit_partial_with_errors(client, tmp_path):
    save_team_config(tmp_path, _valid_config())
    resp = client.post(
        "/team/edit/coder",
        data={"member": "Cody", "model": "DeepSeek-V4"},
    )
    assert resp.status_code == 200
    content = resp.text
    assert '<input name="model"' in content
    assert "格式" in content or "横线" in content


def test_get_row_returns_view_partial_for_cancel(client, tmp_path):
    save_team_config(tmp_path, _valid_config())
    resp = client.get("/team/row/coder")
    assert resp.status_code == 200
    assert "Cody" in resp.text
    assert "<input name=" not in resp.text
