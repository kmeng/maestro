"""Pure calculation layer for dispatch savings.

Both scripts/render_savings.py (Markdown renderer, Epic 6) and the
Web UI route GET /savings (Epic 7, T7.3) consume this module. The
module is responsible for: parsing JSONL rows, filtering superseded
entries, computing per-row costs, and aggregating by task / by role.

Per design 65 §3.1. T7.2 will extend this module with group_by_time
and resolve_log_path.

Determinism contract: given the same input rows, all functions in
this module produce byte-identical output across runs (stable sort
keys, no datetime.now(), no random iteration).
"""

import datetime as dt
import json
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 1. Constants
# ---------------------------------------------------------------------------

# Provider rates (USD per 1M tokens) — snapshot 2026-05-10.
# Updates require an explicit code change so historical pages remain
# reproducible from the same JSONL + the renderer at the time of render.
PROVIDER_RATES_USD_PER_M_TOKENS: dict[str, dict[str, float]] = {
    "claude-opus-4-7":   {"input": 15.0, "output": 75.0},
    "deepseek-v4-pro":   {"input":  0.27, "output": 1.10},
    "deepseek-v4-flash": {"input":  0.07, "output": 0.27},
}

OPUS_MODEL = "claude-opus-4-7"

SCHEMA_VERSION_EXPECTED = 1

# Default dispatch-log location. Mirrors
# bootstrap/maestro_server.py:_DEFAULT_DISPATCH_LOG_PATH so the writer
# (server) and the readers (renderer + Web UI) agree by construction.
_DEFAULT_DISPATCH_LOG_PATH = (
    Path(__file__).resolve().parent.parent / "docs" / "data" / "dispatch-log.jsonl"
)


# ---------------------------------------------------------------------------
# 2. read_rows
# ---------------------------------------------------------------------------

def _parse_dt(s: str) -> dt.datetime:
    """Parse ISO-8601 with trailing Z; tolerant of Python < 3.11 quirks."""
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return dt.datetime.fromisoformat(s)


def read_rows_with_skipped(path: Path) -> tuple[list[dict], int]:
    """Like ``read_rows`` but also returns the count of malformed/skipped lines.

    skipped count = number of lines that failed to parse as JSON, plus
    rows that parsed but had a missing or unparseable ``started_at``.
    Blank lines and ``#``-prefixed comments are NOT counted.

    The Web UI savings page (T7.4) surfaces this count as a footnote
    so users can tell when their JSONL has integrity issues; the
    Markdown renderer ignores the count and uses ``read_rows``.
    """
    if not path.exists():
        return [], 0

    rows: list[dict] = []
    skipped = 0
    with path.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError:
                print(
                    f"⚠ skipping malformed JSON on line {lineno} of {path}",
                    file=sys.stderr,
                )
                skipped += 1
                continue

            if obj.get("schema_version") != SCHEMA_VERSION_EXPECTED:
                print(
                    f"⚠ row {lineno}: schema_version {obj.get('schema_version')} "
                    f"!= expected {SCHEMA_VERSION_EXPECTED}",
                    file=sys.stderr,
                )

            try:
                started = _parse_dt(obj["started_at"])
            except (KeyError, ValueError) as exc:
                print(f"⚠ row {lineno}: bad started_at — {exc}", file=sys.stderr)
                skipped += 1
                continue

            obj["_started_at"] = started
            obj["_duration_seconds"] = float(obj.get("wall_s") or 0.0)

            prompt = obj.get("prompt_tokens")
            completion = obj.get("completion_tokens")
            total = obj.get("total_tokens")
            if prompt is not None and completion is not None:
                obj["_token_count"] = int(prompt) + int(completion)
            elif total is not None:
                obj["_token_count"] = int(total)
            else:
                obj["_token_count"] = 0

            rows.append(obj)
    return rows, skipped


def read_rows(path: Path) -> list[dict]:
    """Return enriched dispatch rows; empty / missing file returns [].

    Thin wrapper over ``read_rows_with_skipped`` that drops the count.
    Preserves the T7.1 calling contract for callers that don't need
    the malformed-row diagnostic.
    """
    rows, _ = read_rows_with_skipped(path)
    return rows


# ---------------------------------------------------------------------------
# 3. compute_costs
# ---------------------------------------------------------------------------

def filter_superseded(rows: list[dict]) -> list[dict]:
    """Drop rows whose row_id is referenced by some other row's `supersedes`.

    Per design 56 §2.1 + ADR-0010: the dispatch log is append-only, so when
    a row's data needs correcting (e.g., backfilling task attribution that
    the server didn't have at dispatch time), the corrected row references
    the original via `supersedes: <row_id>`. Both rows stay in the file
    (audit trail preserves history) but only the latest one in any chain
    is included in aggregation.

    Multi-step chains (X1 supersedes original, X2 supersedes X1) work
    transitively: superseded_ids collects every row referenced by some
    other row's `supersedes`, so X2 is the only survivor.
    """
    superseded_ids = {
        r["supersedes"]
        for r in rows
        if r.get("supersedes")
    }
    return [r for r in rows if r.get("row_id") not in superseded_ids]


def compute_costs(row: dict) -> dict[str, float] | None:
    """Worker + Opus-baseline costs in USD; None when model unknown.

    50/50 split when only `total_tokens` is present (footnoted on the
    rendered page). Opus baseline is a CONSERVATIVE lower bound: real
    Opus tokens for the same task would typically be more, not fewer.
    """
    model = row.get("model")
    if model not in PROVIDER_RATES_USD_PER_M_TOKENS:
        return None

    worker_rates = PROVIDER_RATES_USD_PER_M_TOKENS[model]
    opus_rates = PROVIDER_RATES_USD_PER_M_TOKENS[OPUS_MODEL]

    prompt = row.get("prompt_tokens")
    completion = row.get("completion_tokens")
    total = row.get("total_tokens")

    if prompt is not None and completion is not None:
        input_tokens = int(prompt)
        output_tokens = int(completion)
    elif total is not None:
        input_tokens = int(total) // 2
        output_tokens = int(total) - input_tokens
    else:
        input_tokens = 0
        output_tokens = 0

    worker_in = (input_tokens * worker_rates["input"]) / 1_000_000
    worker_out = (output_tokens * worker_rates["output"]) / 1_000_000
    worker_total = worker_in + worker_out

    opus_in = (input_tokens * opus_rates["input"]) / 1_000_000
    opus_out = (output_tokens * opus_rates["output"]) / 1_000_000
    opus_total = opus_in + opus_out

    saved = opus_total - worker_total
    saved_pct = (saved / opus_total * 100) if opus_total > 0 else 0.0

    return {
        "worker_input_usd": worker_in,
        "worker_output_usd": worker_out,
        "worker_total_usd": worker_total,
        "opus_total_usd": opus_total,
        "saved_usd": saved,
        "saved_pct": saved_pct,
    }


# ---------------------------------------------------------------------------
# 4. group_by_task
# ---------------------------------------------------------------------------

def group_by_task(rows: list[dict]) -> list[dict]:
    """Aggregate enriched rows by task_id; null task_id → 'unattributed'.

    Sort: issue_number DESC (None bucket last), tiebreak by earliest
    started_at DESC. Sort is stable and deterministic — re-running on the
    same input produces identical output.
    """
    groups: dict[str, list[dict]] = {}
    for row in rows:
        tid = row.get("task_id") or "unattributed"
        groups.setdefault(tid, []).append(row)

    result = []
    for tid, group_rows in groups.items():
        tool_counts: dict[str, int] = {}
        total_tokens = 0
        total_wall = 0.0
        total_worker = 0.0
        total_opus = 0.0
        has_estimate = False
        has_rate_unknown = False

        for row in group_rows:
            tool = row.get("tool", "unknown")
            tool_counts[tool] = tool_counts.get(tool, 0) + 1

            total_tokens += row["_token_count"]
            total_wall += row["_duration_seconds"]

            cost = row.get("_cost")
            if cost is None:
                has_rate_unknown = True
            else:
                total_worker += cost["worker_total_usd"]
                total_opus += cost["opus_total_usd"]

            if row.get("is_estimate"):
                has_estimate = True

        issue = None
        for row in group_rows:
            if (num := row.get("issue_number")) is not None:
                issue = num
                break

        earliest_started = min(row["_started_at"] for row in group_rows)

        result.append({
            "task_id": tid,
            "issue_number": issue,
            "rows": group_rows,
            "stats": {
                "count": len(group_rows),
                "tool_counts": tool_counts,
                "total_tokens": total_tokens,
                "total_wall": total_wall,
                "total_worker_usd": total_worker,
                "total_opus_usd": total_opus,
                "saved_usd": total_opus - total_worker,
                "saved_pct": ((total_opus - total_worker) / total_opus * 100)
                              if total_opus > 0 else 0.0,
                "has_estimate": has_estimate,
                "has_rate_unknown": has_rate_unknown,
            },
            "_earliest_started": earliest_started,
        })

    def sort_key(group):
        issue_num = group["issue_number"]
        if issue_num is not None:
            return (0, -issue_num, -group["_earliest_started"].timestamp())
        return (1, 0, -group["_earliest_started"].timestamp())

    result.sort(key=sort_key)
    return result


# ---------------------------------------------------------------------------
# 5. group_by_role
# ---------------------------------------------------------------------------

def group_by_role(rows: list[dict]) -> tuple[list[dict], int]:
    """Aggregate by tool, EXCLUDING is_estimate=True rows.

    Returns (sorted role groups, count of excluded rows). Footnote on
    the page reports the excluded count so the gap is visible.
    """
    measured_rows = [r for r in rows if not r.get("is_estimate")]
    excluded = len(rows) - len(measured_rows)

    groups: dict[str, list[dict]] = {}
    for row in measured_rows:
        tool = row.get("tool", "unknown")
        groups.setdefault(tool, []).append(row)

    result = []
    for tool, group_rows in sorted(groups.items()):
        cnt = len(group_rows)
        total_tokens = sum(r["_token_count"] for r in group_rows)
        total_wall = sum(r["_duration_seconds"] for r in group_rows)
        total_worker = 0.0
        total_opus = 0.0
        for r in group_rows:
            cost = r.get("_cost")
            if cost is not None:
                total_worker += cost["worker_total_usd"]
                total_opus += cost["opus_total_usd"]

        result.append({
            "tool": tool,
            "rows": group_rows,
            "stats": {
                "count": cnt,
                "total_tokens": total_tokens,
                "avg_tokens_per_call": int(round(total_tokens / cnt)) if cnt else 0,
                "total_wall": total_wall,
                "avg_wall": total_wall / cnt if cnt else 0.0,
                "total_worker_usd": total_worker,
                "total_opus_usd": total_opus,
            },
        })
    return result, excluded


# ---------------------------------------------------------------------------
# 6. group_by_time (T7.2)
# ---------------------------------------------------------------------------

def group_by_time(rows: list[dict], granularity: str = "day") -> list[dict]:
    """Aggregate enriched rows by UTC calendar day; reverse-chronological.

    Per design 65 §2.2.3: the Web UI's per-time table groups dispatches
    by day (UTC) to keep determinism aligned with how `started_at` is
    stored. The granularity parameter is forward-compatible but only
    "day" is implemented in v0.0.3 (week/month deferred per Epic 7 body).

    Each output entry mirrors the group_by_role shape (rows + nested
    stats) so Web UI and Markdown templates can share a row renderer
    if useful later.
    """
    if granularity != "day":
        raise ValueError(
            f"group_by_time granularity must be 'day' in v0.0.3, got {granularity!r}"
        )

    groups: dict[str, list[dict]] = {}
    for row in rows:
        # _started_at is a tz-aware datetime (see read_rows). Convert
        # to UTC before extracting the calendar day so the bucket key
        # is independent of the input timezone offset.
        key = row["_started_at"].astimezone(dt.timezone.utc).strftime("%Y-%m-%d")
        groups.setdefault(key, []).append(row)

    result = []
    for date_key, group_rows in groups.items():
        cnt = len(group_rows)
        total_tokens = sum(r["_token_count"] for r in group_rows)
        total_wall = sum(r["_duration_seconds"] for r in group_rows)
        total_worker = 0.0
        total_opus = 0.0
        for r in group_rows:
            cost = r.get("_cost")
            if cost is not None:
                total_worker += cost["worker_total_usd"]
                total_opus += cost["opus_total_usd"]

        result.append({
            "date": date_key,
            "rows": group_rows,
            "stats": {
                "count": cnt,
                "total_tokens": total_tokens,
                "total_wall": total_wall,
                "total_worker_usd": total_worker,
                "total_opus_usd": total_opus,
                "saved_usd": total_opus - total_worker,
                "saved_pct": ((total_opus - total_worker) / total_opus * 100)
                              if total_opus > 0 else 0.0,
            },
        })

    # Reverse-chronological (most recent day first). YYYY-MM-DD strings
    # sort correctly lexicographically.
    result.sort(key=lambda g: g["date"], reverse=True)
    return result


# ---------------------------------------------------------------------------
# 7. resolve_log_path (T7.2)
# ---------------------------------------------------------------------------

def resolve_log_path() -> tuple[Path, str]:
    """Resolve dispatch-log path + classification for the savings UI.

    Honors MAESTRO_DISPATCH_LOG per Epic 6 / design 56 §2.2 semantics:
    - env var unset → default path
    - env var empty string → telemetry disabled
    - env var non-empty → that path

    Returns ``(path, source)`` where ``source`` is one of:
    - ``"default"`` — env unset, default path resolved AND exists on disk
    - ``"env"`` — env set to non-empty, that path resolved AND exists
    - ``"missing"`` — path resolved (default or env) but file does NOT exist
    - ``"disabled"`` — env explicitly empty string; telemetry off

    Never raises. Web UI route uses ``source`` to pick the template
    (happy / empty / disabled); T7.4 wires the error template for the
    distinct "file exists but unreadable" case via read_rows() raising.
    """
    raw = os.environ.get("MAESTRO_DISPATCH_LOG")

    if raw is None:
        path = _DEFAULT_DISPATCH_LOG_PATH
        source = "default"
    elif raw == "":
        # Disabled — surface the default path for display only; the
        # caller branches on source, not path.
        return _DEFAULT_DISPATCH_LOG_PATH, "disabled"
    else:
        path = Path(raw)
        source = "env"

    if not path.exists():
        source = "missing"
    return path, source
