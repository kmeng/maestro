import re

import pytest
from pydantic import ValidationError

from maestro.team import DEFAULT_MODELS, ROLE_IDS, RoleEntry, TeamConfig


def _valid_roles_dict() -> dict[str, dict[str, str]]:
    """Return a fresh dict of 4 valid role inputs for happy-path / mutation tests."""
    return {
        "coder": {"member": "Cody", "model": "deepseek-v4-pro"},
        "librarian": {"member": "Lily", "model": "deepseek-v4-flash"},
        "reviewer": {"member": "Rae", "model": "deepseek-v4-pro"},
        "scribe": {"member": "Sage", "model": "deepseek-v4-flash"},
    }


def test_role_id_accepts_canonical_four():
    cfg = TeamConfig(schema_version=1, roles=_valid_roles_dict())
    assert cfg.schema_version == 1
    assert set(cfg.roles.keys()) == {"coder", "librarian", "reviewer", "scribe"}


def test_role_id_rejects_unknown_role():
    roles = _valid_roles_dict()
    roles["architect"] = {"member": "Archy", "model": "deepseek-v4-flash"}
    with pytest.raises(ValidationError):
        TeamConfig(schema_version=1, roles=roles)


def test_team_config_rejects_missing_role():
    roles = _valid_roles_dict()
    del roles["scribe"]
    with pytest.raises(ValidationError) as exc_info:
        TeamConfig(schema_version=1, roles=roles)
    assert "scribe" in str(exc_info.value)


def test_team_config_rejects_extra_top_level_field():
    with pytest.raises(ValidationError):
        TeamConfig(schema_version=1, roles=_valid_roles_dict(), extra_key="x")


def test_role_entry_rejects_extra_field():
    roles = _valid_roles_dict()
    roles["coder"]["extra"] = "x"
    with pytest.raises(ValidationError):
        TeamConfig(schema_version=1, roles=roles)


def test_member_empty_after_strip_rejected():
    roles = _valid_roles_dict()
    roles["coder"]["member"] = "   "
    with pytest.raises(ValidationError):
        TeamConfig(schema_version=1, roles=roles)


def test_member_too_long_rejected():
    roles = _valid_roles_dict()
    roles["coder"]["member"] = "a" * 65
    with pytest.raises(ValidationError):
        TeamConfig(schema_version=1, roles=roles)


@pytest.mark.parametrize("bad_member", ["Cody\n", "Cody\t", "Cody\x00", "Cody\x7f"])
def test_member_with_control_char_rejected(bad_member):
    roles = _valid_roles_dict()
    roles["coder"]["member"] = bad_member
    with pytest.raises(ValidationError):
        TeamConfig(schema_version=1, roles=roles)


def test_member_unicode_allowed():
    roles = _valid_roles_dict()
    roles["coder"]["member"] = "科迪"
    cfg = TeamConfig(schema_version=1, roles=roles)
    assert cfg.roles["coder"].member == "科迪"


def test_member_strip_canonicalizes():
    roles = _valid_roles_dict()
    roles["coder"]["member"] = "  Cody  "
    cfg = TeamConfig(schema_version=1, roles=roles)
    assert cfg.roles["coder"].member == "Cody"


def test_model_empty_after_strip_rejected():
    roles = _valid_roles_dict()
    roles["coder"]["model"] = "   "
    with pytest.raises(ValidationError):
        TeamConfig(schema_version=1, roles=roles)


def test_model_too_long_rejected():
    roles = _valid_roles_dict()
    roles["coder"]["model"] = "a" * 129
    with pytest.raises(ValidationError):
        TeamConfig(schema_version=1, roles=roles)


def test_model_regex_rejects_uppercase():
    roles = _valid_roles_dict()
    roles["coder"]["model"] = "DeepSeek-V4"
    with pytest.raises(ValidationError):
        TeamConfig(schema_version=1, roles=roles)


@pytest.mark.parametrize("bad_model", ["-deepseek", ".deepseek", "_deepseek"])
def test_model_regex_rejects_leading_special(bad_model):
    roles = _valid_roles_dict()
    roles["coder"]["model"] = bad_model
    with pytest.raises(ValidationError):
        TeamConfig(schema_version=1, roles=roles)


def test_model_regex_rejects_space():
    roles = _valid_roles_dict()
    roles["coder"]["model"] = "deepseek v4"
    with pytest.raises(ValidationError):
        TeamConfig(schema_version=1, roles=roles)


def test_model_regex_accepts_dots_dashes_underscores():
    roles = _valid_roles_dict()
    roles["coder"]["model"] = "deepseek-v4_pro.test"
    cfg = TeamConfig(schema_version=1, roles=roles)
    assert cfg.roles["coder"].model == "deepseek-v4_pro.test"


def test_schema_version_must_be_one():
    with pytest.raises(ValidationError):
        TeamConfig(schema_version=2, roles=_valid_roles_dict())


def test_duplicate_member_alias_rejected_case_insensitive():
    roles = _valid_roles_dict()
    roles["coder"]["member"] = "Cody"
    roles["librarian"]["member"] = "cody"
    with pytest.raises(ValidationError) as exc_info:
        TeamConfig(schema_version=1, roles=roles)
    msg = str(exc_info.value)
    assert "coder" in msg
    assert "librarian" in msg


def test_duplicate_member_alias_rejected_whitespace_insensitive():
    roles = _valid_roles_dict()
    roles["coder"]["member"] = "Cody"
    roles["librarian"]["member"] = " Cody "
    with pytest.raises(ValidationError) as exc_info:
        TeamConfig(schema_version=1, roles=roles)
    # Error message should include the first occurrence's original casing.
    assert "Cody" in str(exc_info.value)


def test_default_models_keys_cover_role_ids_and_shipped_tools():
    """DEFAULT_MODELS must include an entry for every ROLE_ID and SHIPPED_TOOL_ID."""
    from maestro.team import SHIPPED_TOOL_IDS
    assert set(DEFAULT_MODELS.keys()) == set(ROLE_IDS) | set(SHIPPED_TOOL_IDS)


def test_default_models_values_match_pattern():
    pattern = re.compile(r"[a-z0-9][a-z0-9._-]*")
    for val in DEFAULT_MODELS.values():
        assert pattern.fullmatch(val) is not None, f"Invalid default model: {val}"


def test_default_models_specific_values():
    assert DEFAULT_MODELS == {
        "coder": "deepseek-v4-pro",
        "librarian": "deepseek-v4-flash",
        "reviewer": "deepseek-v4-pro",
        "scribe": "deepseek-v4-flash",
        "verifier": "deepseek-v4-flash",
        "spec-writer": "deepseek-v4-flash",
    }


# T8.2 — SHIPPED_TOOL_IDS + verifier in DEFAULT_MODELS


def test_shipped_tool_ids_includes_verifier():
    from maestro.team import SHIPPED_TOOL_IDS
    assert "verifier" in SHIPPED_TOOL_IDS


def test_shipped_tool_ids_disjoint_from_role_ids():
    """User-configurable roles and shipped tools must not overlap."""
    from maestro.team import SHIPPED_TOOL_IDS
    assert set(SHIPPED_TOOL_IDS).isdisjoint(set(ROLE_IDS))


def test_default_models_includes_every_shipped_tool():
    from maestro.team import SHIPPED_TOOL_IDS
    for tool_id in SHIPPED_TOOL_IDS:
        assert tool_id in DEFAULT_MODELS, f"DEFAULT_MODELS missing {tool_id}"


def test_role_id_literal_includes_verifier():
    """RoleId Literal extends to include verifier for dispatch lifecycle typing."""
    from maestro.team.models import RoleId
    import typing
    args = typing.get_args(RoleId)
    assert "verifier" in args


def test_team_config_still_rejects_verifier_as_team_yaml_key():
    """team.yaml requires exactly the 4 user roles; verifier must NOT be addable there."""
    roles = _valid_roles_dict()
    roles["verifier"] = {"member": "Val", "model": "deepseek-v4-flash"}
    with pytest.raises(ValidationError, match="roles must contain exactly"):
        TeamConfig(schema_version=1, roles=roles)


def test_shipped_tool_ids_includes_spec_writer():
    from maestro.team import SHIPPED_TOOL_IDS
    assert "spec-writer" in SHIPPED_TOOL_IDS


def test_role_id_literal_includes_spec_writer():
    """T8.3: RoleId Literal extends to include spec-writer for dispatch typing."""
    from maestro.team.models import RoleId
    import typing
    args = typing.get_args(RoleId)
    assert "spec-writer" in args


def test_team_config_still_rejects_spec_writer_as_team_yaml_key():
    """team.yaml requires only the 4 user roles; spec-writer must NOT be addable."""
    roles = _valid_roles_dict()
    roles["spec-writer"] = {"member": "Sam", "model": "deepseek-v4-flash"}
    with pytest.raises(ValidationError, match="roles must contain exactly"):
        TeamConfig(schema_version=1, roles=roles)
