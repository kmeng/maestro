"""GET /api/overview — Aggregated dashboard data for the Overview page (T9.2, Epic 9).

Reads the local dispatch log + savings rows once per call and returns a
single JSON snapshot consumed by the `/` Overview page. No caching — the
data sets are small (kilobyte-scale JSONL) and freshness matters for the
daily-dashboard use case.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from maestro import paths
from maestro.dispatch_log.events import (
    DispatchEndEvent,
    DispatchFailedEvent,
    DispatchFallbackConfigAbsentEvent,
    DispatchRefusedConfigInvalidEvent,
    DispatchStartEvent,
)
from maestro.dispatch_log.reader import scan_log
from maestro.savings import (
    compute_costs,
    filter_superseded,
    read_rows_with_skipped,
    resolve_log_path,
)

router = APIRouter(prefix="/api", tags=["overview"])

# A start without matching end/failed older than this is excluded from now_running.
# Tuned for "a worker process abandoned by the user is not a live dispatch."
IN_FLIGHT_FLOOR_S = 600


@router.get("/overview")
def get_overview() -> dict[str, Any]:
    # Two distinct log files by project convention:
    #   - typed-event stream lives in <project>/.maestro/logs/dispatch.jsonl
    #     (read by /live, /history, /problems; provides start/end/failed events).
    #   - cost-row evidence file is resolved by maestro.savings.resolve_log_path
    #     (default docs/data/dispatch-log.jsonl; provides token + cost rows).
    # The Overview KPIs need both, so we read each from its proper source.
    events_path = paths.dispatch_log_path(Path.cwd()) / "dispatch.jsonl"
    savings_path, savings_source = resolve_log_path()
    if savings_source == "disabled":
        return _empty_response(telemetry="disabled")

    events = scan_log(events_path)

    try:
        rows_raw, _skipped = read_rows_with_skipped(savings_path)
    except FileNotFoundError:
        rows_raw = []
    rows = filter_superseded(rows_raw)

    today_utc = datetime.now(timezone.utc).date()
    yesterday_utc = today_utc - timedelta(days=1)
    now = datetime.now(timezone.utc)

    today_count = 0
    yesterday_count = 0
    all_start_count = 0

    # 7-day window keyed by date, oldest first.
    spark_bucket: dict[Any, int] = {
        today_utc - timedelta(days=6 - i): 0 for i in range(7)
    }

    # Index terminal events first so the in-flight check is O(1) per Start.
    completed: set[str] = set()
    for event in events:
        if isinstance(event, (DispatchEndEvent, DispatchFailedEvent)):
            completed.add(event.request_id)

    in_flight_starts: list[DispatchStartEvent] = []

    for event in events:
        if isinstance(event, DispatchStartEvent):
            all_start_count += 1
            ts_date = event.timestamp.date()
            if ts_date == today_utc:
                today_count += 1
            elif ts_date == yesterday_utc:
                yesterday_count += 1
            if ts_date in spark_bucket:
                spark_bucket[ts_date] += 1

            if (
                event.request_id not in completed
                and (now - event.timestamp).total_seconds() <= IN_FLIGHT_FLOOR_S
            ):
                in_flight_starts.append(event)

    open_problems = sum(
        1
        for e in events
        if isinstance(
            e,
            (
                DispatchFailedEvent,
                DispatchRefusedConfigInvalidEvent,
                DispatchFallbackConfigAbsentEvent,
            ),
        )
    )

    today_savings = 0.0
    cumulative_savings = 0.0
    opus_total = 0.0
    for row in rows:
        cost = compute_costs(row)
        if cost is None:
            continue
        saved = cost.get("saved_usd", 0.0)
        opus = cost.get("opus_total_usd", 0.0)
        cumulative_savings += saved
        opus_total += opus

        started_str = row.get("started_at")
        if started_str:
            try:
                started_dt = datetime.fromisoformat(started_str)
            except ValueError:
                continue
            if started_dt.date() == today_utc:
                today_savings += saved

    if opus_total == 0:
        savings_pct = 0.0
    else:
        savings_pct = round(cumulative_savings / opus_total * 100, 1)

    active_workers = 0
    now_running = None
    if in_flight_starts:
        roles = {e.role for e in in_flight_starts}
        active_workers = len(roles)
        latest = max(in_flight_starts, key=lambda e: e.timestamp)
        elapsed = int((now - latest.timestamp).total_seconds())
        now_running = {
            "role": latest.role,
            "model": latest.model,
            "member": latest.member,
            "input_summary": latest.input_summary,
            "started_at_iso": latest.timestamp.isoformat(),
            "elapsed_s": elapsed,
        }

    sparkline = [
        {"date": day.isoformat(), "count": spark_bucket[day]}
        for day in sorted(spark_bucket.keys())
    ]

    delta = today_count - yesterday_count

    return {
        "telemetry": "active",
        "today": {
            "dispatches": today_count,
            "savings_usd": round(today_savings, 2),
            "delta_dispatches_vs_yesterday": delta,
        },
        "cumulative": {
            "dispatches": all_start_count,
            "savings_usd": round(cumulative_savings, 2),
            "savings_pct": savings_pct,
        },
        "now_running": now_running,
        "active_workers": active_workers,
        "open_problems": open_problems,
        "sparkline_7d": sparkline,
    }


def _empty_response(telemetry: str = "active") -> dict[str, Any]:
    """Zero-state response — used on telemetry-disabled / missing / empty log."""
    return {
        "telemetry": telemetry,
        "today": {
            "dispatches": 0,
            "savings_usd": 0.0,
            "delta_dispatches_vs_yesterday": 0,
        },
        "cumulative": {
            "dispatches": 0,
            "savings_usd": 0.0,
            "savings_pct": 0.0,
        },
        "now_running": None,
        "active_workers": 0,
        "open_problems": 0,
        "sparkline_7d": _zero_sparkline(),
    }


def _zero_sparkline() -> list[dict]:
    """7 entries, oldest first, ending today (UTC), all count=0."""
    today = datetime.now(timezone.utc).date()
    return [
        {"date": (today - timedelta(days=6 - i)).isoformat(), "count": 0}
        for i in range(7)
    ]
