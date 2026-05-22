"""maestro/dispatcher.py — async dispatch lifecycle with model resolution.

Delegates model resolution to maestro.team.resolve.resolve_role_model
(single source of truth per Epic 1 D4); owns dispatch event emission
via maestro.dispatch_log.writer.emit_event."""

import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable

from maestro.dispatch_log.events import (
    DispatchEndEvent,
    DispatchFailedEvent,
    DispatchFallbackConfigAbsentEvent,
    DispatchRefusedConfigInvalidEvent,
    DispatchStartEvent,
)
from maestro.dispatch_log.writer import emit_event
from maestro.team.models import RoleId
from maestro.team.resolve import ResolveRefuse, resolve_role_model


def _to_fallback_event(
    raw: dict, request_id: str, timestamp
) -> DispatchFallbackConfigAbsentEvent:
    """Translate resolve_role_model's dict-event into T3.1 Pydantic event."""
    return DispatchFallbackConfigAbsentEvent(
        request_id=request_id,
        timestamp=timestamp,
        role=raw["role"],
        fallback_model=raw["model"],
    )


def _to_refused_event(
    raw: dict, request_id: str, timestamp
) -> DispatchRefusedConfigInvalidEvent:
    """Translate resolve_role_model's dict-event into T3.1 Pydantic event."""
    return DispatchRefusedConfigInvalidEvent(
        request_id=request_id,
        timestamp=timestamp,
        validation_error_field=f"roles.{raw['role']}",
        validation_error_message=raw["detail"],
    )


async def run(
    role: RoleId,
    input: str,
    executor: Callable[[str], Awaitable[str]],
) -> str:
    """Dispatch a worker invocation: resolve model, emit lifecycle events,
    invoke executor. Returns executor output on success OR structured
    error string on TeamConfigInvalid (no exception). Re-raises any
    executor exception AFTER emitting dispatch.failed."""
    request_id = uuid.uuid4().hex
    project_root = Path.cwd()

    resolution = resolve_role_model(role, project_root)

    if isinstance(resolution, ResolveRefuse):
        emit_event(
            _to_refused_event(resolution.event, request_id, datetime.now(timezone.utc)),
            project_root,
        )
        return resolution.error_message

    if resolution.event is not None:
        emit_event(
            _to_fallback_event(resolution.event, request_id, datetime.now(timezone.utc)),
            project_root,
        )
    model = resolution.model
    member = role

    start_t = time.monotonic()
    emit_event(
        DispatchStartEvent(
            request_id=request_id,
            timestamp=datetime.now(timezone.utc),
            role=role, model=model, member=member, input_summary=input,
        ),
        project_root,
    )

    try:
        output = await executor(model)
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
