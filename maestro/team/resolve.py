"""Maps (role_id, project_root) -> dispatch model or refuse.

Implements design 13 § Failure modes (file level) D4 fallback semantics:
- absent team.yaml → DEFAULT_MODELS fallback with a config_absent event
- valid team.yaml → model from the configured role (no extra event;
  Epic 3 emits start/end events on its own)
- invalid team.yaml → refuse dispatch with a config_invalid event and
  a user-visible error message

Pure resolver — no I/O of its own beyond delegating to load_team_config.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Union

from maestro.team.io import TeamConfigInvalid, load_team_config
from maestro.team.models import DEFAULT_MODELS, ROLE_IDS


@dataclass(frozen=True)
class ResolveOk:
    """Dispatch may proceed using `model`.

    `event` is set when team.yaml was absent and the DEFAULT_MODELS
    fallback was used. Caller emits it best-effort to the dispatch log.
    `event` is None on the normal-valid path — Epic 3 emits start/end
    events on its own.
    """

    model: str
    event: dict | None = None


@dataclass(frozen=True)
class ResolveRefuse:
    """Dispatch must NOT proceed.

    Caller surfaces `error_message` to the invoking client and emits
    `event` to the dispatch log.
    """

    error_message: str
    event: dict


ResolveResult = Union[ResolveOk, ResolveRefuse]


def resolve_role_model(
    role_id: str,
    project_root: Union[Path, str],
) -> ResolveResult:
    """Resolve which model `role_id` should dispatch to, given team.yaml at
    `<project_root>/.maestro/team.yaml`.

    Raises ValueError for unknown role_id (caller bug, not config issue).
    """
    if role_id not in ROLE_IDS:
        raise ValueError(
            f"unknown role_id: {role_id!r}; must be one of {ROLE_IDS}"
        )

    result = load_team_config(project_root)

    if result is None:
        # team.yaml absent — preserve v0.0.2 behaviour via DEFAULT_MODELS.
        fallback_model = DEFAULT_MODELS[role_id]
        return ResolveOk(
            model=fallback_model,
            event={
                "type": "dispatch.fallback.config_absent",
                "role": role_id,
                "model": fallback_model,
            },
        )

    if isinstance(result, TeamConfigInvalid):
        # Surface the first field-level error in the user message for
        # actionability (the wizard can render the full list separately).
        detail = result.reason
        if result.pydantic_error is not None:
            errors = result.pydantic_error.errors()
            if errors:
                first = errors[0]
                loc = ".".join(str(x) for x in first.get("loc", ()))
                msg = first.get("msg", "")
                if loc and msg:
                    detail = f"{result.reason}: {loc} — {msg}"
                elif msg:
                    detail = f"{result.reason}: {msg}"
        error_message = (
            f"team.yaml at .maestro/team.yaml is invalid: {detail}. "
            f"Open the Web UI to fix, or edit the file directly."
        )
        return ResolveRefuse(
            error_message=error_message,
            event={
                "type": "dispatch.refused.config_invalid",
                "role": role_id,
                "detail": detail,
            },
        )

    return ResolveOk(model=result.roles[role_id].model, event=None)
