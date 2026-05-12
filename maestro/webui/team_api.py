"""HTTP API for team.yaml read/write.

Design 13 § Validation rules / § Failure modes.
Uses T1.1 Pydantic models and T1.2 I/O helpers.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from maestro.team import (
    TeamConfig,
    TeamConfigInvalid,
    load_team_config,
    save_team_config,
)


def _project_root() -> Path:
    """Return the project root the API operates on.

    For v0.0.3 the Web UI is launched from the user's project directory,
    so cwd is the project. Tests monkeypatch this. Future Epic 2 will
    let the user pick the project explicitly via the registry.
    """
    return Path.cwd()


router = APIRouter(prefix="/api", tags=["team"])


@router.get("/team")
def get_team():
    """Return the current team config as JSON.

    - 404 if team.yaml does not exist.
    - 200 with the TeamConfig JSON when valid.
    - 422 with structured detail when present-but-invalid.
    """
    result = load_team_config(_project_root())

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="team.yaml not configured",
        )

    if isinstance(result, TeamConfigInvalid):
        detail = _format_invalid_detail(result)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": detail, "reason": result.reason},
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=result.model_dump(),
    )


@router.post("/team")
def post_team(payload: TeamConfig):
    """Save the supplied TeamConfig and return it.

    Pydantic validates the body automatically — invalid payloads come
    back as FastAPI 422 with the standard error envelope. On success
    we write atomically and return the canonicalised config.
    """
    save_team_config(_project_root(), payload)
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=payload.model_dump(),
    )


def _format_invalid_detail(invalid: TeamConfigInvalid) -> list[dict]:
    """Render a TeamConfigInvalid into a FastAPI-style detail list.

    When the failure was a Pydantic ValidationError, surfaces the per-field
    errors (compatible with the 422 shape the wizard renders inline). When
    the failure was a YAML parse error or an empty/non-mapping file,
    returns a single synthetic entry with loc=['<file>'].
    """
    if invalid.pydantic_error is not None:
        out = []
        for err in invalid.pydantic_error.errors():
            entry = {
                "loc": list(err.get("loc", ())),
                "msg": err.get("msg", ""),
                "type": err.get("type", ""),
            }
            out.append(entry)
        return out
    return [
        {
            "loc": ["<file>"],
            "msg": invalid.reason,
            "type": "team_yaml_invalid",
        }
    ]
