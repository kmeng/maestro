"""Load credentials into os.environ from project .env then user credentials.env.

Precedence (highest to lowest):

1. Process environment (already set).
2. Project-local ``.env`` at the repository root.
3. User-global file at ``~/.maestro/credentials.env``.

Missing files are silently ignored (logged at DEBUG). Existing keys are never
overwritten; thus process environment always wins.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from maestro.paths import credentials_env_path

logger = logging.getLogger(__name__)


def _parse_env_file(path: Path) -> dict[str, str]:
    """Parse KEY=VALUE lines from *path* into a dict.

    Rules:
    - If the file does not exist, return an empty dict.
    - Lines that are blank, start with '#', or do not contain '=' are skipped.
    - Surrounding matching single or double quotes around the value are stripped.
    - Whitespace around key and value is stripped.
    - Later occurrences of the same key overwrite earlier ones (last-wins).
    """
    if not path.is_file():
        return {}

    result: dict[str, str] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()

            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]

            result[key] = value

    return result


def _apply_env(values: dict[str, str]) -> None:
    """Set os.environ[k] = v for every k not already present.

    Set-if-absent is what makes precedence work: process env (already in
    os.environ) is never overwritten, so it wins over any file source.
    """
    for k, v in values.items():
        if k not in os.environ:
            os.environ[k] = v


def load_credentials(project_root: Path | None = None) -> None:
    """Load credentials from project .env and user credentials.env into os.environ.

    Precedence: process env > project .env > ~/.maestro/credentials.env.

    *project_root* — when ``None``, defaults to the repository root inferred
    from this file's location. Tests pass an explicit ``Path`` to avoid
    touching the real repo.

    Side-effects only; returns ``None``. Missing files are logged at DEBUG.
    """
    if project_root is None:
        project_root = Path(__file__).resolve().parent.parent

    # Apply project .env first so it takes precedence over the user file
    # (set-if-absent makes load order = precedence order for files).
    proj_env = project_root / ".env"
    if not proj_env.is_file():
        logger.debug("env file not found: %s", proj_env)
    _apply_env(_parse_env_file(proj_env))

    user_path = credentials_env_path()
    if not user_path.is_file():
        logger.debug("env file not found: %s", user_path)
    _apply_env(_parse_env_file(user_path))
