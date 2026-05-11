"""maestro/dispatcher.py — T3.4: dispatcher.run() with model resolution."""

import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from maestro.dispatch_log.events import (
    DispatchEndEvent,
    DispatchFailedEvent,
    DispatchFallbackConfigAbsentEvent,
    DispatchRefusedConfigInvalidEvent,
    DispatchStartEvent,
)
from maestro.dispatch_log.writer import emit_event
from maestro.team.io import TeamConfigInvalid, load_team_config
from maestro.team.models import DEFAULT_MODELS, RoleId


def _extract_first_error(invalid: TeamConfigInvalid) -> tuple[str, str]:
    """Return (field_path, message) from a TeamConfigInvalid.

    Prefers Pydantic's structured errors list when available, falling
    back to the raw reason string for YAML-parse-level failures."""
    if invalid.pydantic_error is not None:
        errs = invalid.pydantic_error.errors()
        if errs:
            first = errs[0]
            field = ".".join(str(p) for p in first.get("loc", ()))
            msg = first.get("msg", invalid.reason)
            return field, msg
    return "", invalid.reason


def run(role: RoleId, input: str, executor: Callable[[str], str]) -> str:
    """Dispatch a worker invocation, recording start/end/failed events."""
    request_id = uuid.uuid4().hex
    project_root = Path.cwd()

    config = load_team_config(project_root)

    if config is None:
        fallback_model = DEFAULT_MODELS[role]
        member = role
        emit_event(
            DispatchFallbackConfigAbsentEvent(
                request_id=request_id,
                timestamp=datetime.now(timezone.utc),
                role=role,
                fallback_model=fallback_model,
            ),
            project_root,
        )
        model = fallback_model

    elif isinstance(config, TeamConfigInvalid):
        field, msg = _extract_first_error(config)
        emit_event(
            DispatchRefusedConfigInvalidEvent(
                request_id=request_id,
                timestamp=datetime.now(timezone.utc),
                validation_error_field=field,
                validation_error_message=msg,
            ),
            project_root,
        )
        return (
            f"team.yaml at .maestro/team.yaml is invalid: {field} — {msg}. "
            "Open the Web UI to fix, or edit the file directly."
        )

    else:
        entry = config.roles[role]
        model = entry.model
        member = entry.member

    start_t = time.monotonic()
    emit_event(
        DispatchStartEvent(
            request_id=request_id,
            timestamp=datetime.now(timezone.utc),
            role=role,
            model=model,
            member=member,
            input_summary=input,
        ),
        project_root,
    )

    try:
        output = executor(model)
    except Exception as e:
        duration_ms = int((time.monotonic() - start_t) * 1000)
        emit_event(
            DispatchFailedEvent(
                request_id=request_id,
                timestamp=datetime.now(timezone.utc),
                duration_ms=duration_ms,
                error_kind=type(e).__name__,
                error_message=str(e),
            ),
            project_root,
        )
        raise

    duration_ms = int((time.monotonic() - start_t) * 1000)
    emit_event(
        DispatchEndEvent(
            request_id=request_id,
            timestamp=datetime.now(timezone.utc),
            output_summary=output,
            duration_ms=duration_ms,
        ),
        project_root,
    )
    return output
