"""Team configuration domain — Pydantic models + YAML I/O.

Public API:
    Models (T1.1):
        TeamConfig, RoleEntry, RoleId, DEFAULT_MODELS, ROLE_IDS
    I/O (T1.2):
        load_team_config, save_team_config, TeamConfigInvalid
"""

from maestro.team.io import (
    TeamConfigInvalid,
    load_team_config,
    save_team_config,
)
from maestro.team.models import (
    DEFAULT_MODELS,
    ROLE_IDS,
    RoleEntry,
    RoleId,
    TeamConfig,
)

__all__ = [
    "DEFAULT_MODELS",
    "ROLE_IDS",
    "RoleEntry",
    "RoleId",
    "TeamConfig",
    "TeamConfigInvalid",
    "load_team_config",
    "save_team_config",
]
