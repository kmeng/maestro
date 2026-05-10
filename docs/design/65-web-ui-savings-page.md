# Design 65 — Web UI savings page (general-user view)

Parent epic: [#65](https://github.com/kmeng/maestro/issues/65).

This design specifies the Web UI page that lets any maestro user — not
just maestro the project itself — see the cost savings from their own
worker dispatches, without first adopting GitHub-issue-driven task
organization.

Companion to design 56 (`docs/design/56-effectiveness-page.md`), which
covers maestro's own public Markdown evidence page. Epic 7 ships the
**general-user counterpart** in the Web UI.

## 1. Audience split (mandatory per `feedback_distinguish_user_from_general.md`)

### 1.1 For maestro the project (dogfooding)

- We already have `docs/savings.md` — the public Markdown evidence page,
  rendered via `scripts/render_savings.py`, committed and linked from
  README. That page stays. It is the version reposted to wiki / blog /
  external readers.
- The Web UI savings page is a **secondary surface** for us. Useful when
  developing locally to see numbers update without re-running the
  Markdown renderer + reloading GitHub.
- Per the post-T6.8 CLAUDE.md mandate, every dispatch we emit carries
  `task_id` + `issue_number`. Per-task aggregation lives in the
  Markdown evidence page (`docs/savings.md`), which is where we look
  for it. The Web UI does **not** render per-task — see §2.2.
- Per-time aggregation is less interesting to us because we already
  organize by task. We will look at it but it is not the headline.

### 1.2 For general users (the primary audience for this epic)

- The Web UI page is the **primary surface**. They have no public
  evidence page — most installations will not commit `docs/savings.md`,
  may not even use git for the data at all.
- They may **never** adopt `task_id`. Per-time + per-role aggregates
  are the universal default and the **only** views the Web UI offers.
  Per-task is intentionally not part of this surface (rationale §2.2).
- Time-aggregation answers the question they actually ask: "did
  maestro save me money this week / today / last month?"
- Some users will run only free / cheap models throughout — the page
  must not embarrass them when "saved $" is small or zero. Show what
  they did dispatch and what it would have cost on Opus, period.
- They may have telemetry disabled (`MAESTRO_DISPATCH_LOG=""`). The
  page must explain the empty state without breaking.

The two views differ in **what is foregrounded**, not in the underlying
calculations. Both consume the same JSONL via the same calc layer.

## 2. Functional design

### 2.1 Route and entry point

- HTTP route: `GET /savings` on the Web UI server (the shell built in
  Epic 0 / T0.4 #22). No auth. Local-only by default per Epic 0's
  binding.
- Linked from the Web UI's main nav (placement TBD with Epic 0).
- Page is a plain server-rendered HTML response. No SPA. htmx is
  available (vendored per T0.4) for the optional refresh affordance
  in §2.4 — not required for v1.

### 2.2 Page structure (top-down)

1. **Header strip** — single sentence:
   `N dispatches across <date-min> – <date-max> · saved $X.YY vs Opus baseline (Z%)`.
   Same calculation as `render_headline()` in `scripts/render_savings.py`,
   reformatted for HTML.

2. **Per-role table** — one row per worker tool (coder / librarian /
   reviewer / scribe). Same columns as design 56 §1.3:
   `Role | Dispatches | Total tokens | Avg tokens/call | Avg wall (s) | Worker $ | Est. Opus $`.
   Aggregates over `is_estimate=false` rows; ⚠ rows excluded with a
   footnote count.

3. **Per-time table** — **one row per UTC calendar day** that has at
   least one dispatch. Columns:
   `Date | Dispatches | Tokens | Worker $ | Est. Opus $ | Saved`.
   Sorted reverse-chronological. UTC chosen for determinism (matches
   how `started_at` is stored). Per-time-granularity toggle is
   explicitly out of scope for v1 (see Epic 7 issue body).

   **Per-task is intentionally not a Web UI view**. Rationale: general
   users may not adopt `task_id` at all, and those who do already have
   the Markdown evidence page (`docs/savings.md`) for the per-task
   view. Adding a conditional fourth table would split the calc / view
   surface for a feature that maestro-the-project gets cleanly from the
   Markdown renderer and that general users do not need. If a user
   demand for in-Web-UI per-task surfaces later, file a follow-up.

4. **Footer strip** — three lines:
   - "Reading from: `<resolved JSONL path>`"
   - "Last dispatch: `<max(started_at)>`" (or "no dispatches yet")
   - "Telemetry: enabled · [how to disable](link to methodology §7)"
     OR "Telemetry: **disabled** (`MAESTRO_DISPATCH_LOG=\"\"`) · how
     to enable" depending on env state.

### 2.3 Empty / degraded states

- **JSONL file does not exist** → render the header strip with zeros,
  skip all tables, show a CTA: "No dispatches recorded yet. Dispatch
  any worker (coder / librarian / reviewer / scribe) and refresh."
- **`MAESTRO_DISPATCH_LOG=""`** → render a single banner explaining
  telemetry is disabled and why nothing is shown; do not attempt to
  read the default path. Banner links to methodology §7.
- **`MAESTRO_DISPATCH_LOG` points to unreadable / malformed path** →
  banner explaining the resolved path failed to read; show the
  exception message and the resolved path; no tables.
- **JSONL has malformed rows mixed with valid rows** → render normally
  with the valid rows; show a small "N malformed rows skipped" note in
  the footer. Same tolerance as `read_rows()` already implements.

### 2.4 Refresh model

For v1: page is a snapshot at request time. User refreshes the
browser to see new dispatches.

Live refresh (htmx polling every Ns, or SSE) is **out of scope for
v1** — listed as a follow-up candidate in §8. Rationale: dispatches
are user-triggered events, not a high-frequency stream; manual refresh
fits the actual usage rhythm and avoids coupling Epic 7 to Epic 3's
SSE infrastructure (which is not yet built).

### 2.5 Visual style

Inherits whatever the Epic 0 web shell establishes (htmx + minimal
CSS, no framework). No new design tokens introduced here. Tables are
plain `<table>` with the shell's default styling. The page does not
need to be "pretty" — it needs to be **legible and trustworthy**.

## 3. Technical design

### 3.1 Calc layer extraction

`scripts/render_savings.py` currently mixes two responsibilities:
calculation (read JSONL → groups + costs) and Markdown rendering. The
Web UI needs the calculation half but not the Markdown half.

**Refactor**: extract pure-calc functions into a new module
`bootstrap/savings.py`. Both `scripts/render_savings.py` and the Web UI
route import from it.

Functions moving to `bootstrap/savings.py`:

- `_parse_dt(s)` — datetime parser
- `read_rows(path)` — JSONL reader, comment/blank tolerance
- `filter_superseded(rows)` — supersedes resolution
- `compute_costs(row)` — per-row $ computation against `PROVIDER_RATES`
- `group_by_task(rows)` — per-task aggregation
- `group_by_role(rows)` — per-role aggregation
- `PROVIDER_RATES_USD_PER_M_TOKENS` constant — single source of truth
- A **new** `group_by_time(rows, granularity="day")` function — per-day
  aggregation; granularity arg present from day one but only `"day"` is
  implemented (future-proofs without speculation; trivial parameter,
  cheap to leave in place).
- A **new** `resolve_log_path()` helper — returns
  `(path, source)` where `source ∈ {"default", "env", "disabled",
  "missing"}`. Both `render_savings.py` and the Web UI use it so the
  `MAESTRO_DISPATCH_LOG` semantics live in one place.

Functions staying in `scripts/render_savings.py`:

- All `render_*` functions (Markdown output)
- `_tool_breakdown_str` (helper for Markdown table cell)
- `atomic_write`, `main`

**Determinism contract**: after refactor, `python scripts/render_savings.py`
must produce a `docs/savings.md` byte-identical to the pre-refactor
file. This is the regression test for the extraction.

### 3.2 Web UI route

```python
# bootstrap/web/routes/savings.py  (path TBD with Epic 0)

def savings_view(request):
    log_path, source = bootstrap.savings.resolve_log_path()
    if source == "disabled":
        return render_template("savings_disabled.html")
    if source == "missing":
        return render_template("savings_empty.html", path=log_path)
    try:
        rows = bootstrap.savings.read_rows(log_path)
    except Exception as e:
        return render_template("savings_error.html", path=log_path, error=str(e))
    rows = bootstrap.savings.filter_superseded(rows)
    ctx = {
        "headline": _headline_ctx(rows),
        "per_role": bootstrap.savings.group_by_role(rows),
        "per_time": bootstrap.savings.group_by_time(rows, "day"),
        "log_path": log_path,
        "telemetry_enabled": True,
    }
    return render_template("savings.html", **ctx)
```

Exact framework / template engine deferred to Epic 0's choices. The
above sketch holds regardless (read JSONL → calc → render).

### 3.3 Templates

Five templates, all small (one screen each):

- `savings.html` — full page (header + per-role + per-time + footer)
- `savings_disabled.html` — telemetry-off banner only
- `savings_empty.html` — JSONL missing CTA only
- `savings_error.html` — error banner with diagnostic info
- (Optional) `_savings_table_*.html` partials per table if the main
  template gets unwieldy — judgement call at implementation time.

### 3.4 Performance

JSONL is small in practice. At 25 dispatches today (Epic 6 close),
file is ~10 KB. Even at 10,000 dispatches it stays under 5 MB. We
read + parse + group on every request without caching. If a future
deployment hits performance issues, add a TTL cache then; **do not
preempt with caching now** (premature abstraction per CLAUDE.md tone
guidance).

### 3.5 Tests

- `tests/test_savings_calc.py` — pure-calc tests for the extracted
  module (covers `read_rows`, `filter_superseded`, `compute_costs`,
  `group_by_task`, `group_by_role`, `group_by_time`, `resolve_log_path`).
  These are mostly migrations of existing tests in
  `tests/test_render_savings*.py`; the migration must keep coverage
  even/equal, no regressions.
- `tests/test_savings_view.py` — route-level tests:
  - happy path
  - empty-state (no JSONL)
  - disabled-state (`MAESTRO_DISPATCH_LOG=""`)
  - error-state (unreadable path)
- A determinism regression test: render `docs/savings.md` via the
  refactored `scripts/render_savings.py` and assert byte-equal to the
  committed file. Catches calc-layer drift.

## 4. Failure modes

| Mode | Behaviour |
|---|---|
| JSONL missing | empty-state CTA; HTTP 200 |
| JSONL malformed (some rows) | render valid rows, footnote skipped count |
| JSONL malformed (all rows / fundamentally broken file) | error template with diagnostic |
| `MAESTRO_DISPATCH_LOG=""` | telemetry-disabled banner, no read attempt |
| `MAESTRO_DISPATCH_LOG=<unreadable>` | error template, surfaces exception |
| Unknown model in `PROVIDER_RATES` | row marked ⚠ rate-unknown in tables; aggregates exclude it (same as Markdown renderer) |
| All rows are error-only (no `_banner` data) | header zeros, per-role mostly empty, per-time may render dispatch counts only — explicit display, no crash |
| Concurrent dispatch writes during page load | line-atomic appends + read-time snapshot; at worst one in-flight row appears next refresh |

## 5. Affected modules

- **New**: `bootstrap/savings.py` — extracted calc core
- **Modified**: `scripts/render_savings.py` — switch to importing from
  `bootstrap.savings`; remove duplicated functions; preserve byte-identical
  output as the regression contract
- **New**: web route + templates (paths follow Epic 0's choices —
  expected `bootstrap/web/routes/savings.py` and
  `bootstrap/web/templates/savings*.html`)
- **New**: `tests/test_savings_calc.py`, `tests/test_savings_view.py`
- **No edit**: `docs/savings.md`, `docs/savings-methodology.md`,
  `docs/data/dispatch-log.jsonl` — content / format unchanged
- **No edit**: README.md, CLAUDE.md — Epic 7's surface is the Web UI,
  not the docs surface

## 6. Dependencies

- **Hard**: Epic 0 / T0.4 #22 (Web shell + vendored htmx). Epic 7
  implementation tasks block on T0.4. **Design can land now**;
  implementation tasks get filed but cannot start until the shell exists.
- **None**: Epic 3 (live execution-flow / SSE). Per-page polling /
  SSE for live updates is deferred (§2.4).
- **None**: T6.8's dispatch-parameter attribution. The Web UI does not
  render per-task, so `task_id` presence does not affect this surface
  (it still matters for the Markdown evidence page, which is Epic 6).

## 7. Sub-task breakdown (preview)

To be filed as sub-issues under #65 after design approval:

1. **T7.1** — Extract calc core from `render_savings.py` to
   `bootstrap/savings.py`. Migrate tests. Determinism gate: re-rendered
   `docs/savings.md` is byte-identical. **No Web UI dependency** — can
   run before Epic 0 lands.
2. **T7.2** — Add `group_by_time(rows, "day")` + `resolve_log_path()` to
   `bootstrap/savings.py`. Tests. Standalone calc additions.
3. **T7.3** — Web UI route `GET /savings` + happy-path template (header
   + per-role + per-time + footer). Depends on Epic 0 / T0.4.
4. **T7.4** — Empty / disabled / error state templates + tests. Depends
   on T7.3.
5. **T7.5** — End-to-end verification: spin up Web UI on a project with
   real dispatch data, verify the four states render correctly in a
   browser. Manual smoke test logged in journal.

T7.1 + T7.2 are unblocked today. T7.3 onward waits on T0.4.

## 8. Deferred / out of scope (recap from Epic 7 issue body)

- Per-time granularity toggle (week / month) — wait until a user asks
- Live refresh via htmx polling or SSE — wait until manual refresh
  proves insufficient
- Multi-project aggregation, accounts, remote upload
- Trend charts (sparkline / line chart for per-time)
- CI determinism gate — Epic 6 deferred to v0.0.4
- Worker MCP schema purity — separate Epic 5 bug

## 9. Open questions

1. **Web UI nav placement** — where does the link to `/savings` sit in
   Epic 0's nav? Defer to T7.3 implementation; out of scope here.
2. **Should the page show orchestrator-side cost** (Opus tokens
   consumed by the main session)? Out of scope for Epic 7 — methodology
   page §5 explicitly lists this as a known measurement gap. Surfacing
   it in the UI would require new measurement infrastructure (a
   different epic).

## 10. ADR follow-up

No ADR planned for this epic. The technical decisions (calc-layer
extraction location, snapshot-not-stream rendering, no caching, single
granularity for v1) are all reversible and small; ADR weight not
warranted. If T7.3 implementation surfaces a non-obvious choice, add an
ADR at that point.
