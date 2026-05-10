"""Team configuration domain — Pydantic models + YAML I/O + role resolver.

Public API:
    Models (T1.1):
        TeamConfig, RoleEntry, RoleId, DEFAULT_MODELS, ROLE_IDS
    I/O (T1.2):
        load_team_config, save_team_config, TeamConfigInvalid
    Resolver (T1.6):
        resolve_role_model, ResolveOk, ResolveRefuse
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
from maestro.team.resolve import (
    ResolveOk,
    ResolveRefuse,
    resolve_role_model,
)

__all__ = [
    "DEFAULT_MODELS",
    "ROLE_IDS",
    "ResolveOk",
    "ResolveRefuse",
    "RoleEntry",
    "RoleId",
    "TeamConfig",
    "TeamConfigInvalid",
    "load_team_config",
    "resolve_role_model",
    "save_team_config",
]
