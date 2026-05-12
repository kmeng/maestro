"""Web UI problem panel view (T3.9, Epic 3).

Filtered scan of dispatch.jsonl: failures, config refusals, and grouped
fallbacks. CTAs route back to Epic 1's team config surfaces. Per-session
acknowledge fades a row but does not persist. Chinese labels per D6.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from maestro import paths
from maestro.dispatch_log.events import (
    DispatchEvent,
    DispatchFailedEvent,
    DispatchFallbackConfigAbsentEvent,
    DispatchRefusedConfigInvalidEvent,
    DispatchStartEvent,
)
from maestro.dispatch_log.reader import scan_log

router = APIRouter()


@dataclass
class FailureRow:
    request_id: str
    time_hms: str
    time_iso: str
    role: str
    error_kind: str
    error_message: str


@dataclass
class RefusalRow:
    request_id: str
    time_hms: str
    time_iso: str
    validation_error_field: str
    validation_error_message: str


@dataclass
class FallbackGroup:
    role: str
    fallback_model: str
    count: int


def _format_time_hms(ts: datetime) -> str:
    """Format datetime as HH:MM:SS in local time."""
    return ts.astimezone().strftime("%H:%M:%S")


def _format_time_iso(ts: datetime) -> str:
    """Format datetime as ISO 8601."""
    return ts.isoformat()


def _categorize(
    events: list[DispatchEvent],
) -> tuple[list[FailureRow], list[RefusalRow], list[FallbackGroup]]:
    """Walk events; bin failed / refused / fallback. Group fallbacks by (role, fallback_model)."""
    starts: dict[str, DispatchStartEvent] = {}
    for ev in events:
        if isinstance(ev, DispatchStartEvent):
            starts[ev.request_id] = ev

    failures: list[FailureRow] = []
    refusals: list[RefusalRow] = []
    fallback_counts: dict[tuple[str, str], int] = {}

    for ev in events:
        if isinstance(ev, DispatchFailedEvent):
            role = starts[ev.request_id].role if ev.request_id in starts else "—"
            failures.append(
                FailureRow(
                    request_id=ev.request_id,
                    time_hms=_format_time_hms(ev.timestamp),
                    time_iso=_format_time_iso(ev.timestamp),
                    role=role,
                    error_kind=ev.error_kind,
                    error_message=ev.error_message,
                )
            )
        elif isinstance(ev, DispatchRefusedConfigInvalidEvent):
            refusals.append(
                RefusalRow(
                    request_id=ev.request_id,
                    time_hms=_format_time_hms(ev.timestamp),
                    time_iso=_format_time_iso(ev.timestamp),
                    validation_error_field=ev.validation_error_field,
                    validation_error_message=ev.validation_error_message,
                )
            )
        elif isinstance(ev, DispatchFallbackConfigAbsentEvent):
            key = (ev.role, ev.fallback_model)
            fallback_counts[key] = fallback_counts.get(key, 0) + 1

    failures.sort(key=lambda r: r.time_iso, reverse=True)
    refusals.sort(key=lambda r: r.time_iso, reverse=True)

    fallback_groups = [
        FallbackGroup(role=role, fallback_model=model, count=count)
        for (role, model), count in fallback_counts.items()
    ]
    return failures, refusals, fallback_groups


@router.get("/problems", response_class=HTMLResponse)
async def problem_panel(request: Request) -> HTMLResponse:
    from maestro.webui import templates  # late-bind: avoids name collision with templates/ subdir during pytest collection
    log_path = paths.dispatch_log_path(Path.cwd()) / "dispatch.jsonl"
    events = scan_log(log_path)
    failures, refusals, fallback_groups = _categorize(events)
    has_any = bool(failures or refusals or fallback_groups)
    return templates.TemplateResponse(
        request,
        "problem_panel.html",
        {
            "failures": failures,
            "refusals": refusals,
            "fallback_groups": fallback_groups,
            "has_any": has_any,
        },
    )
