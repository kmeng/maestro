from pathlib import Path

import pytest

from maestro.team import (
    DEFAULT_MODELS,
    ROLE_IDS,
    RoleEntry,
    TeamConfig,
    save_team_config,
)
from maestro.team.resolve import (
    ResolveOk,
    ResolveRefuse,
    resolve_role_model,
)


def _save_valid_config(project_root: Path, **role_model_overrides: str) -> None:
    """Save a valid team.yaml under project_root. Optional overrides
    let a test pin a non-default model on a specific role."""
    roles = {
        "coder": RoleEntry(member="Cody", model=role_model_overrides.get("coder", DEFAULT_MODELS["coder"])),
        "librarian": RoleEntry(member="Lily", model=role_model_overrides.get("librarian", DEFAULT_MODELS["librarian"])),
        "reviewer": RoleEntry(member="Rae", model=role_model_overrides.get("reviewer", DEFAULT_MODELS["reviewer"])),
        "scribe": RoleEntry(member="Sage", model=role_model_overrides.get("scribe", DEFAULT_MODELS["scribe"])),
    }
    save_team_config(project_root, TeamConfig(schema_version=1, roles=roles))


def test_resolve_absent_returns_default_with_event(tmp_path: Path):
    result = resolve_role_model("coder", tmp_path)
    assert isinstance(result, ResolveOk)
    assert result.model == DEFAULT_MODELS["coder"]
    assert result.event is not None
    assert result.event["type"] == "dispatch.fallback.config_absent"
    assert result.event["role"] == "coder"
    assert result.event["model"] == DEFAULT_MODELS["coder"]


def test_resolve_valid_returns_configured_model(tmp_path: Path):
    _save_valid_config(tmp_path, coder="deepseek-v4-pro-test")
    result = resolve_role_model("coder", tmp_path)
    assert isinstance(result, ResolveOk)
    assert result.model == "deepseek-v4-pro-test"
    assert result.event is None


def test_resolve_invalid_yaml_returns_refuse(tmp_path: Path):
    dirpath = tmp_path / ".maestro"
    dirpath.mkdir(parents=True)
    (dirpath / "team.yaml").write_text(": : :")
    result = resolve_role_model("coder", tmp_path)
    assert isinstance(result, ResolveRefuse)
    assert "team.yaml" in result.error_message
    assert "invalid" in result.error_message.lower()
    assert result.event["type"] == "dispatch.refused.config_invalid"


def test_resolve_invalid_validation_error_includes_field_in_message(tmp_path: Path):
    dirpath = tmp_path / ".maestro"
    dirpath.mkdir(parents=True)
    (dirpath / "team.yaml").write_text(
        "schema_version: 2\nroles:\n  coder:\n    member: Cody\n    model: deepseek-v4-pro\n"
    )
    result = resolve_role_model("coder", tmp_path)
    assert isinstance(result, ResolveRefuse)
    assert "schema_version" in result.error_message
    assert result.event["role"] == "coder"


@pytest.mark.parametrize("role", ROLE_IDS)
def test_resolve_each_canonical_role(tmp_path: Path, role: str):
    _save_valid_config(tmp_path)
    result = resolve_role_model(role, tmp_path)
    assert isinstance(result, ResolveOk)
    assert result.model == DEFAULT_MODELS[role]


def test_resolve_unknown_role_raises_value_error(tmp_path: Path):
    with pytest.raises(ValueError) as exc_info:
        resolve_role_model("architect", tmp_path)
    msg = str(exc_info.value)
    assert "architect" in msg
    assert "role_id" in msg


@pytest.mark.parametrize("role", ROLE_IDS)
def test_resolve_absent_each_role(tmp_path: Path, role: str):
    result = resolve_role_model(role, tmp_path)
    assert isinstance(result, ResolveOk)
    assert result.model == DEFAULT_MODELS[role]
    assert result.event is not None
    assert result.event["role"] == role


def test_resolve_refuse_event_payload_shape(tmp_path: Path):
    dirpath = tmp_path / ".maestro"
    dirpath.mkdir(parents=True)
    (dirpath / "team.yaml").write_text(": : :")
    result = resolve_role_model("coder", tmp_path)
    assert isinstance(result, ResolveRefuse)
    assert set(result.event.keys()) == {"type", "role", "detail"}


def test_resolve_fallback_event_payload_shape(tmp_path: Path):
    result = resolve_role_model("librarian", tmp_path)
    assert isinstance(result, ResolveOk)
    assert result.event is not None
    assert set(result.event.keys()) == {"type", "role", "model"}


def test_resolve_valid_does_not_emit_event(tmp_path: Path):
    _save_valid_config(tmp_path)
    result = resolve_role_model("reviewer", tmp_path)
    assert isinstance(result, ResolveOk)
    assert result.event is None


# T8.2 — shipped-tool bypass (verifier)


def test_resolve_role_model_accepts_verifier_returns_default_model(tmp_path: Path):
    """Shipped tools bypass team.yaml; resolver returns DEFAULT_MODELS directly."""
    result = resolve_role_model("verifier", tmp_path)
    assert isinstance(result, ResolveOk)
    assert result.model == DEFAULT_MODELS["verifier"]
    assert result.event is None


def test_resolve_role_model_verifier_works_without_team_yaml(tmp_path: Path):
    """Verifier path is independent of team.yaml presence — no .maestro dir needed."""
    # tmp_path is empty; no .maestro/team.yaml exists
    result = resolve_role_model("verifier", tmp_path)
    assert isinstance(result, ResolveOk)
    assert result.model == "deepseek-v4-flash"


def test_resolve_role_model_verifier_ignores_team_yaml_even_if_present(tmp_path: Path):
    """Even if team.yaml has all 4 user roles, verifier still bypasses it."""
    _save_valid_config(tmp_path)
    result = resolve_role_model("verifier", tmp_path)
    assert isinstance(result, ResolveOk)
    assert result.model == DEFAULT_MODELS["verifier"]
    assert result.event is None


def test_resolve_role_model_rejects_unknown_role(tmp_path: Path):
    """A role in neither ROLE_IDS nor SHIPPED_TOOL_IDS is a caller bug."""
    with pytest.raises(ValueError, match="unknown role_id"):
        resolve_role_model("nonsense", tmp_path)
