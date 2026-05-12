"""Web UI savings view (T7.3, Epic 7).

Renders the per-role + per-time savings tables for the *general user*
of maestro, reading the local dispatch-log.jsonl via the shared
maestro.savings calc layer.

Per design 65 §2.1 / §2.2 / §3.2. T7.3 ships the happy path; T7.4
will replace the three degraded-state placeholders with proper
templates (empty / disabled / error).
"""

from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from maestro.savings import (
    compute_costs,
    filter_superseded,
    group_by_role,
    group_by_time,
    read_rows_with_skipped,
    resolve_log_path,
)

router = APIRouter()


def _headline_ctx(rows: list[dict]) -> dict:
    """Aggregate scalars for the header strip (design 65 §2.2.1).

    Returns the minimum a single-sentence header needs: dispatch count,
    earliest + latest started_at (UTC ISO short form), summed costs,
    and the conservative-lower-bound saving. Empty rows produce zeros
    and an em-dash for the date range — the page still renders rather
    than 500'ing.
    """
    if not rows:
        return {
            "count": 0,
            "total_tokens": 0,
            "date_min": "—",
            "date_max": "—",
            "total_worker_usd": 0.0,
            "total_opus_usd": 0.0,
            "saved_usd": 0.0,
            "saved_pct": 0.0,
        }

    count = len(rows)
    total_tokens = sum(r["_token_count"] for r in rows)
    worker = 0.0
    opus = 0.0
    for r in rows:
        cost = r.get("_cost")
        if cost is not None:
            worker += cost["worker_total_usd"]
            opus += cost["opus_total_usd"]
    saved = opus - worker
    pct = (saved / opus * 100) if opus > 0 else 0.0

    starts = [r["_started_at"] for r in rows]
    return {
        "count": count,
        "total_tokens": total_tokens,
        "date_min": min(starts).strftime("%Y-%m-%d"),
        "date_max": max(starts).strftime("%Y-%m-%d"),
        "total_worker_usd": worker,
        "total_opus_usd": opus,
        "saved_usd": saved,
        "saved_pct": pct,
    }


def _last_dispatch_iso(rows: list[dict]) -> Optional[str]:
    """Latest started_at as ISO-8601 Z, or None when rows is empty."""
    if not rows:
        return None
    return max(r["_started_at"] for r in rows).strftime("%Y-%m-%dT%H:%M:%SZ")


@router.get("/savings", response_class=HTMLResponse)
async def savings_view(request: Request) -> HTMLResponse:
    # Late-bind to avoid name collision with the templates/ subdir
    # during pytest collection (matches history_view / live_view pattern).
    from maestro.webui import templates

    log_path, source = resolve_log_path()

    if source == "disabled":
        return templates.TemplateResponse(request, "savings_disabled.html", {})
    if source == "missing":
        return templates.TemplateResponse(
            request, "savings_empty.html", {"log_path": str(log_path)}
        )
    try:
        rows, skipped_count = read_rows_with_skipped(log_path)
    except Exception as exc:
        return templates.TemplateResponse(
            request,
            "savings_error.html",
            {"log_path": str(log_path), "error": str(exc)},
        )

    rows = filter_superseded(rows)
    for r in rows:
        r["_cost"] = compute_costs(r)

    role_groups, excluded = group_by_role(rows)
    time_groups = group_by_time(rows)

    ctx = {
        "headline": _headline_ctx(rows),
        "per_role": role_groups,
        "excluded_count": excluded,
        "per_time": time_groups,
        "log_path": str(log_path),
        "last_dispatch": _last_dispatch_iso(rows),
        "telemetry_enabled": True,
        "skipped_count": skipped_count,
    }
    return templates.TemplateResponse(request, "savings.html", ctx)
