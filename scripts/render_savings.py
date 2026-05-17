#!/usr/bin/env python3
"""Render docs/savings.md from docs/data/dispatch-log.jsonl.

Pure read → aggregate → write. Deterministic: re-running on the same
JSONL produces byte-identical output (sorted keys, fixed timestamp
sourced from rows, no datetime.now()).

Per design 56 § 4 + § 5. Methodology page (docs/savings-methodology.md)
documents the formulas and gaps; this renderer links to it via relative
path even though the methodology page itself lands in T6.4.

Since T7.1 (Epic 7) the calc layer lives in maestro/savings.py and
is shared with the Web UI route GET /savings (relocated from
bootstrap/savings.py in fix #86).
"""

import sys
from pathlib import Path

# Project root on sys.path so `from maestro.savings import ...` works
# when invoked directly as `python scripts/render_savings.py`. Pytest
# already injects the root via rootdir discovery, so this is a no-op
# under test.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from maestro.savings import (
    PROVIDER_RATES_USD_PER_M_TOKENS,
    compute_costs,
    filter_superseded,
    group_by_role,
    group_by_task,
    read_rows,
    resolve_log_path,
)

# ---------------------------------------------------------------------------
# 1. Constants
# ---------------------------------------------------------------------------

REPO_ROOT = _PROJECT_ROOT
OUT_PATH  = REPO_ROOT / "docs" / "savings.md"


# ---------------------------------------------------------------------------
# 6. render_per_task_table
# ---------------------------------------------------------------------------

def _tool_breakdown_str(tool_counts: dict[str, int]) -> str:
    """Render e.g. '3 (c1 l1 r1 s0 v0 w0)' in fixed coder/librarian/reviewer/scribe/verifier/spec-writer order."""
    c = tool_counts.get("coder", 0)
    l = tool_counts.get("librarian", 0)
    r = tool_counts.get("reviewer", 0)
    s = tool_counts.get("scribe", 0)
    v = tool_counts.get("verifier", 0)
    w = tool_counts.get("spec-writer", 0)
    return f"{sum(tool_counts.values())} (c{c} l{l} r{r} s{s} v{v} w{w})"


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
    # Honors MAESTRO_DISPATCH_LOG via the shared resolver (T7.2). When
    # the env var is unset, this falls back to the project's canonical
    # default — same path the script used to hardcode, so the
    # determinism gate stays valid.
    jsonl_path, _source = resolve_log_path()
    rows = read_rows(jsonl_path)
    rows = filter_superseded(rows)
    for row in rows:
        row["_cost"] = compute_costs(row)

    content = render_full(rows)
    atomic_write(OUT_PATH, content)
    print(f"rendered {OUT_PATH} from {len(rows)} row(s)")


if __name__ == "__main__":
    main()
