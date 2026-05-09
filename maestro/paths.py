"""
Maestro filesystem path definitions — single source of truth for file locations.

This module is the contract between the Web UI process and the MCP server process
for where shared state lives on disk. Both processes import paths from here rather
than hardcoding directory structures.

Paths fall into two categories:
  - User-global (~/.maestro/): credentials, settings, project registry.
  - Project-local (<project>/.maestro/): team configuration, dispatch logs.

This module performs pure path computation only. It does not create directories
or files; callers are responsible for that on first write.
"""

from pathlib import Path
from typing import Union


def user_home() -> Path:
    """Return ~/.maestro/ — the user-global Maestro directory."""
    return Path.home() / ".maestro"


def credentials_env_path() -> Path:
    """Return ~/.maestro/credentials.env — user-global API credentials file."""
    return user_home() / "credentials.env"


def projects_registry_path() -> Path:
    """Return ~/.maestro/projects.json — recent-projects registry."""
    return user_home() / "projects.json"


def user_settings_path() -> Path:
    """Return ~/.maestro/settings.yaml — user preferences (theme, default port, etc.)."""
    return user_home() / "settings.yaml"


def project_home(project_root: Union[Path, str]) -> Path:
    """Return <project_root>/.maestro/ — project-local Maestro directory.

    Accepts both Path objects and strings. Strings are converted to Path
    internally before joining.
    """
    if isinstance(project_root, str):
        project_root = Path(project_root)
    return project_root / ".maestro"


def team_config_path(project_root: Union[Path, str]) -> Path:
    """Return <project_root>/.maestro/team.yaml — role→model bindings (Epic 1 schema)."""
    return project_home(project_root) / "team.yaml"


def dispatch_log_path(project_root: Union[Path, str]) -> Path:
    """Return <project_root>/.maestro/logs/ — directory holding dispatch event log files.

    Note: this returns the logs directory, not a specific file. The dispatch log writer
    (Epic 3) decides the concrete filename and rotation scheme. Returning a directory keeps
    paths.py decoupled from log-format decisions.
    """
    return project_home(project_root) / "logs"
