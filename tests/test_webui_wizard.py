"""Tests for the first-launch wizard (T1.4)."""

import pytest
from fastapi.testclient import TestClient

from maestro.team import (
    DEFAULT_MODELS,
    RoleEntry,
    TeamConfig,
    load_team_config,
    save_team_config,
)


def _custom_config() -> TeamConfig:
    """Return a TeamConfig with non-default member aliases for prefill tests."""
    return TeamConfig(
        schema_version=1,
        roles={
            "coder": RoleEntry(member="codex", model=DEFAULT_MODELS["coder"]),
            "librarian": RoleEntry(member="libby", model=DEFAULT_MODELS["librarian"]),
            "reviewer": RoleEntry(member="revvy", model=DEFAULT_MODELS["reviewer"]),
            "scribe": RoleEntry(member="scrib", model=DEFAULT_MODELS["scribe"]),
        },
    )


@pytest.fixture
def app(monkeypatch, tmp_path):
    """Provide the configured Web UI app pointing at an isolated tmp_path."""
    monkeypatch.setattr("maestro.webui.team_api._project_root", lambda: tmp_path)
    from maestro.webui import app as configured_app

    return configured_app


@pytest.fixture
def client(app):
    return TestClient(app)


def test_get_wizard_renders_step1(client):
    response = client.get("/wizard")
    assert response.status_code == 200
    assert "下一步" in response.text
    assert "Maestro" in response.text


def test_step2_prefills_default_alias_and_models_when_no_team_yaml(client):
    response = client.post("/wizard/step2")
    assert response.status_code == 200
    # Default aliases
    assert 'value="Cody"' in response.text
    assert 'value="Lily"' in response.text
    assert 'value="Rae"' in response.text
    assert 'value="Sage"' in response.text
    # Default models — verify each role's default appears
    for model in DEFAULT_MODELS.values():
        assert f'value="{model}"' in response.text


def test_step2_prefills_existing_team_yaml(client, tmp_path):
    save_team_config(tmp_path, _custom_config())
    response = client.post("/wizard/step2")
    assert response.status_code == 200
    assert 'value="codex"' in response.text
    assert 'value="libby"' in response.text
    assert 'value="revvy"' in response.text
    assert 'value="scrib"' in response.text


def test_validate_field_returns_empty_on_valid_value(client):
    response = client.post(
        "/wizard/validate-field",
        data={"role": "coder", "field": "member", "value": "Cody"},
    )
    assert response.status_code == 200
    assert 'class="field-error"' not in response.text


def test_validate_field_returns_chinese_error_on_invalid(client):
    response = client.post(
        "/wizard/validate-field",
        data={"role": "coder", "field": "model", "value": "DeepSeek-V4"},
    )
    assert response.status_code == 200
    assert "格式" in response.text


def test_validate_field_returns_chinese_error_on_empty_member(client):
    response = client.post(
        "/wizard/validate-field",
        data={"role": "coder", "field": "member", "value": "   "},
    )
    assert response.status_code == 200
    assert "不能为空" in response.text


def test_step3_validates_and_renders_summary_on_success(client):
    data = {
        "member_coder": "Cody",
        "model_coder": DEFAULT_MODELS["coder"],
        "member_librarian": "Lily",
        "model_librarian": DEFAULT_MODELS["librarian"],
        "member_reviewer": "Rae",
        "model_reviewer": DEFAULT_MODELS["reviewer"],
        "member_scribe": "Sage",
        "model_scribe": DEFAULT_MODELS["scribe"],
    }
    response = client.post("/wizard/step3", data=data)
    assert response.status_code == 200
    assert "Cody" in response.text
    assert "Lily" in response.text
    assert "Rae" in response.text
    assert "Sage" in response.text
    assert "保存" in response.text
    assert "返回修改" in response.text


def test_step3_renders_step2_with_errors_on_validation_failure(client):
    data = {
        "member_coder": "Cody",
        "model_coder": DEFAULT_MODELS["coder"],
        "member_librarian": "cody",  # case-insensitive duplicate of coder.member
        "model_librarian": DEFAULT_MODELS["librarian"],
        "member_reviewer": "Rae",
        "model_reviewer": DEFAULT_MODELS["reviewer"],
        "member_scribe": "Sage",
        "model_scribe": DEFAULT_MODELS["scribe"],
    }
    response = client.post("/wizard/step3", data=data)
    assert response.status_code == 200
    # Should re-render step2 (the form) — fieldset legends present.
    assert "<fieldset" in response.text
    # Some field error rendered (per-field span uses .field-error class
    # in the new design — replaces the legacy .error-banner element).
    assert "field-error" in response.text


def test_save_writes_team_yaml_and_renders_step4(client, tmp_path):
    data = {
        "member_coder": "Cody",
        "model_coder": DEFAULT_MODELS["coder"],
        "member_librarian": "Lily",
        "model_librarian": DEFAULT_MODELS["librarian"],
        "member_reviewer": "Rae",
        "model_reviewer": DEFAULT_MODELS["reviewer"],
        "member_scribe": "Sage",
        "model_scribe": DEFAULT_MODELS["scribe"],
    }
    response = client.post("/wizard/save", data=data)
    assert response.status_code == 200
    assert "团队组建完成" in response.text

    team_yaml = tmp_path / ".maestro" / "team.yaml"
    assert team_yaml.is_file()
    loaded = load_team_config(tmp_path)
    assert isinstance(loaded, TeamConfig)
    assert loaded.roles["coder"].member == "Cody"
    assert loaded.roles["coder"].model == DEFAULT_MODELS["coder"]


def test_cancel_link_does_not_write(client, tmp_path):
    response = client.post("/wizard/step2")
    assert response.status_code == 200
    assert 'href="/"' in response.text
    team_yaml = tmp_path / ".maestro" / "team.yaml"
    assert not team_yaml.exists()
