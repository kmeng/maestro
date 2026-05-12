"""Web UI history view (T3.7, Epic 3).

One-shot scan of dispatch.jsonl on page load; events folded by
request_id into reverse-chronological rows. Chinese labels per the
design's D6 cross-cutting language rule.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from maestro import paths
from maestro.dispatch_log.events import (
    CostBreakdown,
    DispatchEndEvent,
    DispatchEvent,
    DispatchFailedEvent,
    DispatchFallbackConfigAbsentEvent,
    DispatchRefusedConfigInvalidEvent,
    DispatchStartEvent,
)
from maestro.dispatch_log.reader import scan_log

router = APIRouter()


@dataclass
class HistoryRow:
    request_id: str
    status: str
    status_icon: str
    status_label_zh: str
    time_hms: str
    time_iso: str
    role_member: str
    model: str
    duration: str
    cost: str
    summary: str
    summary_truncated: bool
    input_summary_full: str
    output_summary_full: str
    error_kind: str
    error_message: str
    validation_error_field: str
    validation_error_message: str
    has_fallback_flag: bool


def _format_time_hms(ts: datetime) -> str:
    """Format datetime as HH:MM:SS in local time."""
    return ts.astimezone().strftime("%H:%M:%S")


def _format_time_iso(ts: datetime) -> str:
    """Format datetime as ISO 8601 (for hover tooltip). Uses datetime.isoformat() to
    preserve actual tz offset rather than hardcoding 'Z' — consistent with problem_panel."""
    return ts.isoformat()


def _format_duration(duration_ms: Optional[int]) -> str:
    """Format duration into Chinese units."""
    if duration_ms is None:
        return "—"
    if duration_ms >= 1000:
        seconds = duration_ms / 1000.0
        return f"{seconds:.1f} 秒"
    return f"{duration_ms} 毫秒"


def _format_cost(cost: Optional[CostBreakdown]) -> str:
    """Format cost as token count arrow or placeholder."""
    if cost is None:
        return "—"
    return f"{cost.prompt_tokens}→{cost.completion_tokens} tok"


def _build_row(request_id: str, slot: dict) -> HistoryRow:
    if "end" in slot:
        status, icon, label = "success", "✓", "成功"
        primary = slot.get("start") if "start" in slot else slot["end"]
    elif "failed" in slot:
        status, icon, label = "failed", "✗", "失败"
        primary = slot.get("start") if "start" in slot else slot["failed"]
    elif "refused" in slot:
        status, icon, label = "refused", "⊘", "已拒绝"
        primary = slot["refused"]
    elif "start" in slot:
        status, icon, label = "in_progress", "◐", "进行中"
        primary = slot["start"]
    elif "fallback" in slot:
        status, icon, label = "fallback_only", "↩", "已降级"
        primary = slot["fallback"]
    else:
        raise ValueError(f"empty slot for request_id={request_id}")

    time_hms = _format_time_hms(primary.timestamp)
    time_iso = _format_time_iso(primary.timestamp)

    if isinstance(primary, DispatchStartEvent):
        role_member = f"{primary.role} / {primary.member}"
    elif isinstance(primary, DispatchFallbackConfigAbsentEvent):
        role_member = primary.role
    else:
        role_member = getattr(primary, "role", "—")
        if role_member != "—" and hasattr(primary, "member") and primary.member:
            role_member = f"{role_member} / {primary.member}"

    if isinstance(primary, DispatchStartEvent):
        model = primary.model
    elif isinstance(primary, DispatchFallbackConfigAbsentEvent):
        model = primary.fallback_model
    else:
        model = "—"

    if "end" in slot:
        duration = _format_duration(slot["end"].duration_ms)
    elif "failed" in slot:
        duration = _format_duration(slot["failed"].duration_ms)
    else:
        duration = "—"

    if "end" in slot:
        cost = _format_cost(slot["end"].cost)
    else:
        cost = "—"

    start_ev = slot.get("start")
    if start_ev is not None and isinstance(start_ev, DispatchStartEvent):
        input_summary_full = start_ev.input_summary
    else:
        input_summary_full = ""

    summary = input_summary_full[:60] if len(input_summary_full) > 60 else input_summary_full
    summary_truncated = len(input_summary_full) > 60

    if "end" in slot and isinstance(slot["end"], DispatchEndEvent):
        output_summary_full = slot["end"].output_summary
    else:
        output_summary_full = ""

    if "failed" in slot and isinstance(slot["failed"], DispatchFailedEvent):
        error_kind = slot["failed"].error_kind
        error_message = slot["failed"].error_message
    else:
        error_kind = ""
        error_message = ""

    if "refused" in slot and isinstance(slot["refused"], DispatchRefusedConfigInvalidEvent):
        validation_error_field = slot["refused"].validation_error_field
        validation_error_message = slot["refused"].validation_error_message
    else:
        validation_error_field = ""
        validation_error_message = ""

    has_fallback_flag = "fallback" in slot and status != "fallback_only"

    return HistoryRow(
        request_id=request_id,
        status=status,
        status_icon=icon,
        status_label_zh=label,
        time_hms=time_hms,
        time_iso=time_iso,
        role_member=role_member,
        model=model,
        duration=duration,
        cost=cost,
        summary=summary,
        summary_truncated=summary_truncated,
        input_summary_full=input_summary_full,
        output_summary_full=output_summary_full,
        error_kind=error_kind,
        error_message=error_message,
        validation_error_field=validation_error_field,
        validation_error_message=validation_error_message,
        has_fallback_flag=has_fallback_flag,
    )


def _fold_events(events: list[DispatchEvent]) -> list[HistoryRow]:
    """Fold events by request_id into HistoryRow objects."""
    by_id: dict[str, dict] = {}
    for ev in events:
        rid = ev.request_id
        slot = by_id.setdefault(rid, {})
        if isinstance(ev, DispatchStartEvent):
            slot["start"] = ev
        elif isinstance(ev, DispatchEndEvent):
            slot["end"] = ev
        elif isinstance(ev, DispatchFailedEvent):
            slot["failed"] = ev
        elif isinstance(ev, DispatchRefusedConfigInvalidEvent):
            slot["refused"] = ev
        elif isinstance(ev, DispatchFallbackConfigAbsentEvent):
            slot["fallback"] = ev

    return [_build_row(rid, slot) for rid, slot in by_id.items()]


@router.get("/history", response_class=HTMLResponse)
async def history_view(request: Request) -> HTMLResponse:
    from maestro.webui import templates  # late-bind: avoids name collision with templates/ subdir during pytest collection
    log_path = paths.dispatch_log_path(Path.cwd()) / "dispatch.jsonl"
    events = scan_log(log_path)
    rows = _fold_events(events)
    rows.sort(key=lambda r: r.time_iso, reverse=True)
    return templates.TemplateResponse(request, "history.html", {"rows": rows})
