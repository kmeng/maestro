"""Pytest tests for maestro.env_loader covering precedence, parsing, and edge cases."""
import logging
import os
from pathlib import Path


from maestro import env_loader


def test_process_env_wins_over_both_files(tmp_path: Path, monkeypatch) -> None:
    """Process environment value is not overwritten by any file."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "from_proc")

    (tmp_path / ".env").write_text("DEEPSEEK_API_KEY=from_proj\n")
    user_env = tmp_path / "creds.env"
    user_env.write_text("DEEPSEEK_API_KEY=from_user\n")
    monkeypatch.setattr(env_loader, "credentials_env_path", lambda: user_env)

    env_loader.load_credentials(project_root=tmp_path)
    assert os.environ["DEEPSEEK_API_KEY"] == "from_proc"


def test_project_env_wins_over_user_file(tmp_path: Path, monkeypatch) -> None:
    """Project .env overrides the user credentials file."""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    (tmp_path / ".env").write_text("DEEPSEEK_API_KEY=from_proj\n")
    user_env = tmp_path / "creds.env"
    user_env.write_text("DEEPSEEK_API_KEY=from_user\n")
    monkeypatch.setattr(env_loader, "credentials_env_path", lambda: user_env)

    env_loader.load_credentials(project_root=tmp_path)
    assert os.environ["DEEPSEEK_API_KEY"] == "from_proj"


def test_user_file_resolves_when_others_miss(tmp_path: Path, monkeypatch) -> None:
    """User file value is used when process env and project .env are absent."""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    user_env = tmp_path / "creds.env"
    user_env.write_text("DEEPSEEK_API_KEY=from_user\n")
    monkeypatch.setattr(env_loader, "credentials_env_path", lambda: user_env)

    env_loader.load_credentials(project_root=tmp_path)
    assert os.environ["DEEPSEEK_API_KEY"] == "from_user"


def test_v0_0_2_compat_project_env_only(tmp_path: Path, monkeypatch) -> None:
    """Works with only the project .env present (backward compatibility AC4)."""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    (tmp_path / ".env").write_text("DEEPSEEK_API_KEY=from_proj\n")
    user_env = tmp_path / "no_user.env"
    monkeypatch.setattr(env_loader, "credentials_env_path", lambda: user_env)

    env_loader.load_credentials(project_root=tmp_path)
    assert os.environ["DEEPSEEK_API_KEY"] == "from_proj"


def test_missing_user_file_silent(tmp_path: Path, monkeypatch, caplog) -> None:
    """When user file is missing, a DEBUG log is emitted and no error raised."""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    (tmp_path / ".env").write_text("DEEPSEEK_API_KEY=from_proj\n")
    user_env = tmp_path / "does_not_exist.env"
    monkeypatch.setattr(env_loader, "credentials_env_path", lambda: user_env)

    with caplog.at_level(logging.DEBUG, logger="maestro.env_loader"):
        env_loader.load_credentials(project_root=tmp_path)

    assert os.environ["DEEPSEEK_API_KEY"] == "from_proj"
    assert any(str(user_env) in rec.message for rec in caplog.records), \
        "Missing file not logged"


def test_missing_both_files_silent(tmp_path: Path, monkeypatch) -> None:
    """Both files missing: no exception, key remains unset."""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    user_env = tmp_path / "no_creds.env"
    monkeypatch.setattr(env_loader, "credentials_env_path", lambda: user_env)

    env_loader.load_credentials(project_root=tmp_path)
    assert os.environ.get("DEEPSEEK_API_KEY") is None


def test_set_if_absent_does_not_overwrite_existing_keys(tmp_path: Path, monkeypatch) -> None:
    """Existing os.environ keys are not overwritten by file values."""
    monkeypatch.setenv("FOO", "proc")
    (tmp_path / ".env").write_text("FOO=file\n")
    user_env = tmp_path / "creds.env"
    user_env.write_text("FOO=user\n")
    monkeypatch.setattr(env_loader, "credentials_env_path", lambda: user_env)

    env_loader.load_credentials(project_root=tmp_path)
    assert os.environ["FOO"] == "proc"


def test_parse_strips_quotes_and_comments(tmp_path: Path, monkeypatch) -> None:
    """Parsing rules: blank lines, comments, quoted values, whitespace stripping."""
    for key in ("KEY", "KEY2", "BARE", "WITH_SPACES"):
        monkeypatch.delenv(key, raising=False)

    content = (
        'KEY="quoted"\n'
        '\n'
        '# comment\n'
        "KEY2='single'\n"
        'BARE=value\n'
        'WITH_SPACES = trimmed \n'
        'no equal line\n'
    )
    (tmp_path / ".env").write_text(content)
    monkeypatch.setattr(env_loader, "credentials_env_path", lambda: tmp_path / "absent")

    env_loader.load_credentials(project_root=tmp_path)

    assert os.environ["KEY"] == "quoted"
    assert os.environ["KEY2"] == "single"
    assert os.environ["BARE"] == "value"
    assert os.environ["WITH_SPACES"] == "trimmed"


def test_later_value_wins_within_single_file(tmp_path: Path, monkeypatch) -> None:
    """Within one file, the last occurrence of a key wins."""
    monkeypatch.delenv("K", raising=False)

    (tmp_path / ".env").write_text("K=first\nK=second\n")
    monkeypatch.setattr(env_loader, "credentials_env_path", lambda: tmp_path / "absent")

    env_loader.load_credentials(project_root=tmp_path)
    assert os.environ["K"] == "second"


def test_user_file_used_via_paths_module(tmp_path: Path, monkeypatch) -> None:
    """Loader uses the path returned by maestro.paths.credentials_env_path."""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    user_env = tmp_path / "custom_creds.env"
    user_env.write_text("DEEPSEEK_API_KEY=via_paths\n")
    monkeypatch.setattr(env_loader, "credentials_env_path", lambda: user_env)

    env_loader.load_credentials(project_root=tmp_path)
    assert os.environ["DEEPSEEK_API_KEY"] == "via_paths"
