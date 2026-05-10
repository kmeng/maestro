"""Team configuration domain — Pydantic models + default model bindings.

Public API:
    TeamConfig, RoleEntry, RoleId, DEFAULT_MODELS, ROLE_IDS

Pure data layer. YAML I/O lives in maestro.team.io (T1.2).
"""

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
]
