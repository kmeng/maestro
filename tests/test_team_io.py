import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from maestro.team import (
    DEFAULT_MODELS,
    TeamConfig,
    RoleEntry,
    TeamConfigInvalid,
    load_team_config,
    save_team_config,
)


def _valid_config() -> TeamConfig:
    """Build a fresh valid TeamConfig from DEFAULT_MODELS + canonical aliases."""
    return TeamConfig(
        schema_version=1,
        roles={
            "coder": RoleEntry(member="Cody", model=DEFAULT_MODELS["coder"]),
            "librarian": RoleEntry(member="Lily", model=DEFAULT_MODELS["librarian"]),
            "reviewer": RoleEntry(member="Rae", model=DEFAULT_MODELS["reviewer"]),
            "scribe": RoleEntry(member="Sage", model=DEFAULT_MODELS["scribe"]),
        },
    )


def test_load_returns_none_when_file_absent(tmp_path: Path):
    assert load_team_config(tmp_path) is None
    # load is read-only, must not create .maestro directory
    assert not (tmp_path / ".maestro").exists()


def test_save_then_load_round_trip(tmp_path: Path):
    config = _valid_config()
    save_team_config(tmp_path, config)

    loaded = load_team_config(tmp_path)
    assert isinstance(loaded, TeamConfig)
    assert loaded.schema_version == config.schema_version
    assert loaded.model_dump()["roles"] == config.model_dump()["roles"]


def test_save_creates_dot_maestro_directory(tmp_path: Path):
    dot_maestro = tmp_path / ".maestro"
    assert not dot_maestro.is_dir()

    save_team_config(tmp_path, _valid_config())

    assert dot_maestro.is_dir()
    assert (dot_maestro / "team.yaml").is_file()


def test_saved_file_contains_header_comment(tmp_path: Path):
    save_team_config(tmp_path, _valid_config())
    raw = (tmp_path / ".maestro" / "team.yaml").read_text(encoding="utf-8")
    assert "Maestro 团队配置" in raw
    assert "schema_version: 1" in raw


def test_load_returns_invalid_on_yaml_parse_error(tmp_path: Path):
    dot_maestro = tmp_path / ".maestro"
    dot_maestro.mkdir(parents=True)
    (dot_maestro / "team.yaml").write_text(": : :", encoding="utf-8")

    result = load_team_config(tmp_path)
    assert isinstance(result, TeamConfigInvalid)
    assert result.pydantic_error is None
    assert "yaml" in result.reason.lower()


def test_load_returns_invalid_on_validation_error(tmp_path: Path):
    yaml_text = (
        "schema_version: 2\n"
        "roles:\n"
        "  coder: {member: Cody, model: deepseek-v4-pro}\n"
        "  librarian: {member: Lily, model: deepseek-v4-flash}\n"
        "  reviewer: {member: Rae, model: deepseek-v4-pro}\n"
        "  scribe: {member: Sage, model: deepseek-v4-flash}\n"
    )
    dot_maestro = tmp_path / ".maestro"
    dot_maestro.mkdir(parents=True)
    (dot_maestro / "team.yaml").write_text(yaml_text, encoding="utf-8")

    result = load_team_config(tmp_path)
    assert isinstance(result, TeamConfigInvalid)
    assert result.pydantic_error is not None
    assert isinstance(result.pydantic_error, ValidationError)
    reason_low = result.reason.lower()
    assert "validation" in reason_low or "schema" in reason_low


def test_load_returns_invalid_on_unknown_role(tmp_path: Path):
    yaml_text = (
        "schema_version: 1\n"
        "roles:\n"
        "  coder: {member: Cody, model: deepseek-v4-pro}\n"
        "  librarian: {member: Lily, model: deepseek-v4-flash}\n"
        "  reviewer: {member: Rae, model: deepseek-v4-pro}\n"
        "  scribe: {member: Sage, model: deepseek-v4-flash}\n"
        "  architect: {member: Archy, model: deepseek-v4-flash}\n"
    )
    dot_maestro = tmp_path / ".maestro"
    dot_maestro.mkdir(parents=True)
    (dot_maestro / "team.yaml").write_text(yaml_text, encoding="utf-8")

    result = load_team_config(tmp_path)
    assert isinstance(result, TeamConfigInvalid)
    assert result.pydantic_error is not None


def test_load_returns_invalid_on_empty_file(tmp_path: Path):
    dot_maestro = tmp_path / ".maestro"
    dot_maestro.mkdir(parents=True)
    (dot_maestro / "team.yaml").write_text("", encoding="utf-8")

    result = load_team_config(tmp_path)
    assert isinstance(result, TeamConfigInvalid)
    assert result.pydantic_error is None
    assert "empty" in result.reason.lower()


def test_load_returns_invalid_on_top_level_list(tmp_path: Path):
    dot_maestro = tmp_path / ".maestro"
    dot_maestro.mkdir(parents=True)
    (dot_maestro / "team.yaml").write_text("- a\n- b\n", encoding="utf-8")

    result = load_team_config(tmp_path)
    assert isinstance(result, TeamConfigInvalid)
    assert result.pydantic_error is None
    assert "mapping" in result.reason.lower()


def test_save_uses_os_replace(monkeypatch, tmp_path: Path):
    calls = []
    original_replace = os.replace

    def record_replace(src, dst):
        calls.append((src, dst))
        original_replace(src, dst)

    monkeypatch.setattr("maestro.team.io.os.replace", record_replace)

    config = _valid_config()
    save_team_config(tmp_path, config)

    assert len(calls) == 1
    src, dst = calls[0]
    assert src.name.endswith("team.yaml.tmp")
    assert dst.name == "team.yaml"


def test_save_failure_leaves_original_file_intact(monkeypatch, tmp_path: Path):
    # Step 1 – save a valid config
    config_v1 = _valid_config()
    save_team_config(tmp_path, config_v1)

    target = tmp_path / ".maestro" / "team.yaml"
    bytes_v1 = target.read_bytes()

    # Step 3 – different config
    config_v2 = _valid_config()
    config_v2.roles["coder"].member = "NewCody"

    # Step 4 – simulate yaml.safe_dump failure
    monkeypatch.setattr(
        "maestro.team.io.yaml.safe_dump",
        lambda payload, sort_keys, allow_unicode: (_ for _ in ()).throw(RuntimeError("simulated")),
    )

    # Step 5 – expect RuntimeError
    with pytest.raises(RuntimeError, match="simulated"):
        save_team_config(tmp_path, config_v2)

    # Step 6 – original untouched
    assert target.read_bytes() == bytes_v1


def test_save_failure_cleans_up_tmp_file(monkeypatch, tmp_path: Path):
    # Same setup as test 11
    save_team_config(tmp_path, _valid_config())

    monkeypatch.setattr(
        "maestro.team.io.yaml.safe_dump",
        lambda payload, sort_keys, allow_unicode: (_ for _ in ()).throw(RuntimeError("simulated")),
    )

    with pytest.raises(RuntimeError):
        save_team_config(tmp_path, _valid_config())

    # No .tmp file left behind
    dot_maestro = tmp_path / ".maestro"
    tmp_files = list(dot_maestro.glob("*.tmp"))
    assert tmp_files == []


def test_save_overwrites_existing_file(tmp_path: Path):
    config_v1 = _valid_config()
    save_team_config(tmp_path, config_v1)

    config_v2 = _valid_config()
    config_v2.roles["coder"].member = "NewCody"
    save_team_config(tmp_path, config_v2)

    loaded = load_team_config(tmp_path)
    assert isinstance(loaded, TeamConfig)
    assert loaded.roles["coder"].member == "NewCody"
