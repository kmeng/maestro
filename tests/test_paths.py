"""
Tests for maestro/paths.py — verifying path computation contracts.

These tests assert that the path functions return the correct paths
and that no I/O side effects occur during path computation.
"""

from pathlib import Path

from maestro.paths import (
    user_home,
    credentials_env_path,
    projects_registry_path,
    user_settings_path,
    project_home,
    team_config_path,
    dispatch_log_path,
)


def test_user_home_returns_dot_maestro_under_home(monkeypatch, tmp_path):
    """The user-global Maestro directory lives under the user's home directory."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert user_home() == tmp_path / ".maestro"


def test_credentials_env_path_under_user_home(monkeypatch, tmp_path):
    """Credentials file lives inside the user-global Maestro directory."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert credentials_env_path() == tmp_path / ".maestro" / "credentials.env"


def test_projects_registry_path_under_user_home(monkeypatch, tmp_path):
    """Project registry file lives inside the user-global Maestro directory."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert projects_registry_path() == tmp_path / ".maestro" / "projects.json"


def test_user_settings_path_under_user_home(monkeypatch, tmp_path):
    """User settings file lives inside the user-global Maestro directory."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert user_settings_path() == tmp_path / ".maestro" / "settings.yaml"


def test_project_home_with_path_object(tmp_path):
    """Project-local Maestro directory path is computed under the project root."""
    assert project_home(tmp_path) == tmp_path / ".maestro"


def test_project_home_with_string_input(tmp_path):
    """String project roots are converted to Path objects internally."""
    result = project_home(str(tmp_path))
    assert isinstance(result, Path)
    assert result == tmp_path / ".maestro"


def test_project_home_with_trailing_slash(tmp_path):
    """Trailing slashes in string paths are normalized by Path."""
    result = project_home(str(tmp_path) + "/")
    assert result == tmp_path / ".maestro"


def test_team_config_path_under_project_home(tmp_path):
    """Team config file lives inside the project-local Maestro directory."""
    assert team_config_path(tmp_path) == tmp_path / ".maestro" / "team.yaml"


def test_dispatch_log_path_returns_logs_directory(tmp_path):
    """Dispatch log path returns the logs directory, not a specific file.

    We return the directory, not a file — the log writer (Epic 3) owns filename choice.
    """
    assert dispatch_log_path(tmp_path) == tmp_path / ".maestro" / "logs"


def test_paths_does_no_io(monkeypatch, tmp_path):
    """All path functions are pure computation — no files or directories are created."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    user_home()
    credentials_env_path()
    projects_registry_path()
    user_settings_path()
    project_home(tmp_path)
    team_config_path(tmp_path)
    dispatch_log_path(tmp_path)

    assert not (tmp_path / ".maestro").exists()
    assert not (tmp_path / ".maestro" / "credentials.env").exists()
    assert not (tmp_path / ".maestro" / "projects.json").exists()
    assert not (tmp_path / ".maestro" / "settings.yaml").exists()
    assert not (tmp_path / ".maestro" / "team.yaml").exists()
    assert not (tmp_path / ".maestro" / "logs").exists()
