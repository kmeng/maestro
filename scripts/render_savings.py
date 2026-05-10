#!/usr/bin/env python3
"""Render docs/savings.md from docs/data/dispatch-log.jsonl.

Pure read → aggregate → write. Deterministic: re-running on the same
JSONL produces byte-identical output (sorted keys, fixed timestamp
sourced from rows, no datetime.now()).

Per design 56 § 4 + § 5. Methodology page (docs/savings-methodology.md)
documents the formulas and gaps; this renderer links to it via relative
path even though the methodology page itself lands in T6.4.
"""

import datetime as dt
import json
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

REPO_ROOT = Path(__file__).resolve().parent.parent
JSONL_PATH = REPO_ROOT / "docs" / "data" / "dispatch-log.jsonl"
OUT_PATH   = REPO_ROOT / "docs" / "savings.md"
SCHEMA_VERSION_EXPECTED = 1


# ---------------------------------------------------------------------------
# 2. read_rows
# ---------------------------------------------------------------------------

def _parse_dt(s: str) -> dt.datetime:
    """Parse ISO-8601 with trailing Z; tolerant of Python < 3.11 quirks."""
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return dt.datetime.fromisoformat(s)


def read_rows(path: Path) -> list[dict]:
    """Return enriched dispatch rows; empty / missing file returns [].

    Skips blank lines and `#`-prefixed comments. Malformed JSON warns
    to stderr and is skipped. Schema-version mismatches warn but the row
    is still included.

    Enrichment fields (prefixed with underscore so they don't collide
    with the on-disk schema):
      _started_at        datetime
      _duration_seconds  float (sourced from row["wall_s"])
      _token_count       int (sum of prompt+completion, falling back to total)
    """
    if not path.exists():
        return []

    rows: list[dict] = []
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
# 6. render_per_task_table
# ---------------------------------------------------------------------------

def _tool_breakdown_str(tool_counts: dict[str, int]) -> str:
    """Render e.g. '3 (c1 l1 r1 s0)' in fixed coder/lib/rev/scribe order."""
    c = tool_counts.get("coder", 0)
    l = tool_counts.get("librarian", 0)
    r = tool_counts.get("reviewer", 0)
    s = tool_counts.get("scribe", 0)
    return f"{sum(tool_counts.values())} (c{c} l{l} r{r} s{s})"


def render_per_task_table(task_groups: list[dict]) -> str:
    header = "| Task | Closed | Issue | Dispatches | Tokens | Wall (s) | Est. Opus $ | Worker $ | Saved | Status |"
    sep    = "|------|--------|-------|------------|--------|----------|-------------|----------|-------|--------|"
    lines = [header, sep]
    for g in task_groups:
        s = g["stats"]
        tid = g["task_id"] if g["task_id"] != "unattributed" else "—"
        closed = ""  # blank in v0.0.3; explained in methodology page
        issue_str = (
            f"[#{g['issue_number']}](https://github.com/kmeng/maestro/issues/{g['issue_number']})"
            if g["issue_number"] is not None else "—"
        )
        dispatches = _tool_breakdown_str(s["tool_counts"])
        tokens = f"{s['total_tokens']:,}"
        wall = f"{int(round(s['total_wall']))}"
        opus_dollars = f"${s['total_opus_usd']:,.2f}"
        worker_dollars = f"${s['total_worker_usd']:,.2f}"
        saved_dollars = f"${s['saved_usd']:,.2f} ({s['saved_pct']:.1f}%)"
        if s["has_rate_unknown"]:
            status = "rate-unknown ⚠"
        elif s["has_estimate"]:
            status = "⚠"
        else:
            status = "✓"

        lines.append(
            f"| {tid} | {closed} | {issue_str} | {dispatches} | {tokens} | {wall} | "
            f"{opus_dollars} | {worker_dollars} | {saved_dollars} | {status} |"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7. render_per_role_table
# ---------------------------------------------------------------------------

def render_per_role_table(role_groups: list[dict], excluded_count: int) -> str:
    header = "| Role | Dispatches | Total tokens | Avg tokens/call | Avg wall (s) | Total worker $ | Total est. Opus $ |"
    sep    = "|------|------------|---------------|-----------------|--------------|----------------|-------------------|"
    lines = [header, sep]
    for g in role_groups:
        tool = g["tool"].capitalize()
        s = g["stats"]
        lines.append(
            f"| {tool} | {s['count']} | {s['total_tokens']:,} | "
            f"{s['avg_tokens_per_call']} | {s['avg_wall']:.1f} | "
            f"${s['total_worker_usd']:,.2f} | ${s['total_opus_usd']:,.2f} |"
        )
    if excluded_count > 0:
        lines.append("")
        lines.append(f"*{excluded_count} row(s) excluded from this aggregate as ⚠ estimates.*")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 8. render_headline
# ---------------------------------------------------------------------------

def render_headline(rows: list[dict]) -> str:
    if not rows:
        return (
            "No measured dispatches yet. Run a worker after "
            "sourcing scripts/begin_task.sh to populate this page."
        )

    closed = len({r["task_id"] for r in rows if r.get("task_id")})
    total_dispatch = len(rows)
    total_tokens = sum(r["_token_count"] for r in rows)

    total_worker = 0.0
    total_opus = 0.0
    for r in rows:
        cost = r.get("_cost")
        if cost is not None:
            total_worker += cost["worker_total_usd"]
            total_opus += cost["opus_total_usd"]

    saved = total_opus - total_worker
    pct = (saved / total_opus * 100) if total_opus > 0 else 0.0

    return (
        f"Across {closed} closed task(s), {total_dispatch} dispatch(es) captured "
        f"{total_tokens:,} total tokens. At provider rates, this cost "
        f"${total_worker:,.2f}; estimated baseline at Opus rates would be "
        f"${total_opus:,.2f} — a conservative lower-bound saving of "
        f"${saved:,.2f} ({pct:.1f}%). All numbers in the table below come from "
        "worker-API responses captured at dispatch time; see methodology for "
        "what is measured vs estimated."
    )


# ---------------------------------------------------------------------------
# 9. render_full
# ---------------------------------------------------------------------------

def render_full(rows: list[dict]) -> str:
    task_groups = group_by_task(rows)
    role_groups, excluded = group_by_role(rows)

    last_updated = "—"
    if rows:
        max_dt = max(r["_started_at"] for r in rows)
        last_updated = max_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    title = "# Dispatch Savings"
    headline = render_headline(rows)
    task_table = render_per_task_table(task_groups)
    role_table = render_per_role_table(role_groups, excluded)

    return (
        f"{title}\n\n"
        f"{headline}\n\n"
        f"## Per-Task Savings\n\n"
        f"{task_table}\n\n"
        f"## Per-Role Breakdown\n\n"
        f"{role_table}\n\n"
        f"---\n\n"
        f"*Methodology: [docs/savings-methodology.md](savings-methodology.md)*  \n"
        f"*Last updated: {last_updated}*  \n"
        f"*Source: [dispatch-log.jsonl](data/dispatch-log.jsonl)*\n"
    )


# ---------------------------------------------------------------------------
# 10. atomic_write
# ---------------------------------------------------------------------------

def atomic_write(path: Path, content: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


# ---------------------------------------------------------------------------
# 11. main
# ---------------------------------------------------------------------------

def main() -> None:
    rows = read_rows(JSONL_PATH)
    rows = filter_superseded(rows)
    for row in rows:
        row["_cost"] = compute_costs(row)

    content = render_full(rows)
    atomic_write(OUT_PATH, content)
    print(f"rendered {OUT_PATH} from {len(rows)} row(s)")


if __name__ == "__main__":
    main()
