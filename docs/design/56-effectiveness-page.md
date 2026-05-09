# Design 56 — project effectiveness measurement & public landing page

Parent epic: [#56](https://github.com/kmeng/maestro/issues/56).

This design specifies the data pipeline and the rendered page that
backs Maestro's "near-flagship code at 10–20% of the cost" claim with
real measured per-task data, transparently distinguishing measurement
from estimate.

## 1. Functional design

### 1.1 Reader experience

- A reader lands on `README.md`, sees a one-line link near the top
  ("Cost evidence: see `docs/savings.md`") plus a headline number
  badge updated by the renderer.
- Click → `docs/savings.md`, GitHub-rendered, no JS required.
- The page opens with three blocks:
  1. **Headline numbers** — single paragraph: total tasks measured,
     total dispatches, total measured tokens, total estimated $ cost,
     conservative estimated savings vs Opus baseline.
  2. **Per-task table** — one row per closed task, reverse-chronological.
  3. **Per-role aggregate table** — one row per worker role
     (librarian / coder / reviewer / scribe), sorted by total tokens
     descending.
- Below the tables: short "How we measured this" paragraph linking to
  `docs/savings-methodology.md`.
- Footer: last-updated timestamp (read from JSONL, not `now()`) +
  link to the underlying `docs/data/dispatch-log.jsonl`.

### 1.2 Per-task table columns

| Task | Closed | Issue | Dispatches | Tokens | Wall (s) | Est. Opus $ | Worker $ | Saved | Status |
|---|---|---|---|---|---|---|---|---|---|

- **Task** — `T0.3`-style ID linking to its journal section.
- **Closed** — date the task issue was closed.
- **Issue** — `#21` linking to GitHub issue.
- **Dispatches** — count, broken down inline as `c1 l2 r1 s2`
  (coder/librarian/reviewer/scribe).
- **Tokens** — sum across dispatches; cell is bold-measured or
  italic-⚠-estimated depending on row status.
- **Wall (s)** — sum across dispatches.
- **Est. Opus $** — same token count × Opus rate (lower bound
  baseline; see methodology).
- **Worker $** — sum across dispatches at provider rates.
- **Saved** — `Est. Opus $` − `Worker $`, expressed as both `$X.XX`
  and `Y%` of Opus baseline.
- **Status** — ✓ measured, ⚠ estimated (legacy / banner-gap).

### 1.3 Per-role aggregate table columns

| Role | Dispatches | Total tokens | Avg tokens/call | Avg wall (s) | Total worker $ | Total est. Opus $ |
|---|---|---|---|---|---|---|

- Aggregates only over rows where `is_estimate=false`; ⚠ rows excluded
  (counts shown in a footnote so the gap is visible without polluting
  the average).

### 1.4 Contributor experience

After closing a task:

```bash
python scripts/render_savings.py
git add docs/savings.md
git commit -m "docs(savings): refresh after T0.4"
```

The renderer is **deterministic** — running it twice on the same
JSONL produces byte-identical output (sorted keys, fixed timestamp
sourced from JSONL latest row, no `now()`).

For tasks where some dispatches lacked banner data (banner-gap
period), the renderer flags those rows with ⚠ and footnotes which
fields were estimated and via what method.

## 2. Data shape

### 2.1 JSONL row schema (`docs/data/dispatch-log.jsonl`)

One row = one dispatch (worker call). Append-only. No edits, no
deletes; corrections are added as new rows with a `supersedes` field
referencing the row being corrected.

```json
{
  "row_id": "01HW2-T03-coder-1",
  "task_id": "T0.3",
  "issue_number": 21,
  "tool": "coder",
  "model": "deepseek-v4-pro",
  "model_provider": "deepseek",
  "wall_s": 68.98,
  "prompt_tokens": null,
  "completion_tokens": null,
  "total_tokens": 3675,
  "started_at": "2026-05-09T14:32:18Z",
  "journal_ref": "docs/journal/2026-05-09-loop-closed.md#T0.3",
  "is_estimate": false,
  "est_method": null,
  "supersedes": null,
  "schema_version": 1
}
```

Field rules:
- `prompt_tokens` / `completion_tokens` are `null` when banner only
  reports `total_tokens`. Renderer handles this gracefully.
- `is_estimate=true` means **at least one** of the numeric fields was
  filled from estimation rather than measurement; `est_method` says
  which one and how (e.g. `"tokens=heuristic_from_doc_size"`).
- `schema_version` enables forward migration without rewriting
  history.
- `row_id` format: `<ULID-prefix>-<task_id>-<tool>-<seq-within-task>`,
  human-readable and globally unique.

### 2.2 Data file location & control

- Default path: `docs/data/dispatch-log.jsonl` (committed; this is
  the audit trail).
- Override via `MAESTRO_DISPATCH_LOG` env var:
  - **unset / not set** → default path.
  - **non-empty** → that path; useful for private projects or
    redirecting to `/tmp` during pytest.
  - **empty string (`""`)** → telemetry writes are skipped entirely.
- The renderer always reads the default path; if a contributor
  redirects writes elsewhere, they must `cp` it back before
  rendering. Documented in methodology page.

### 2.3 File hygiene

- One row per line, UTF-8, LF line endings.
- Append uses `with open(path, "a", encoding="utf-8") as f: f.write(json.dumps(row) + "\n")`.
- Renderer reads with `for line in open(path): if line.strip(): rows.append(json.loads(line))` — robust to empty/comment lines.
- Comments allowed: lines starting with `#` are ignored by the
  renderer. Used for human annotations during backfill.

## 3. Telemetry source

### 3.1 Approach: structured emit at the dispatch site

The dispatcher in `bootstrap/maestro_server.py` already has
`wall_s` and `total_tokens` in scope when constructing the banner.
Rather than parse banners back from `result_text` (fragile), we add
a single helper called **inside** the dispatch handler:

```python
def _emit_dispatch_row(*, tool, model, wall_s, total_tokens,
                      task_id, issue_number, started_at,
                      prompt_tokens=None, completion_tokens=None):
    log_path_env = os.environ.get("MAESTRO_DISPATCH_LOG")
    if log_path_env == "":
        return  # explicitly disabled
    log_path = Path(log_path_env) if log_path_env else _DEFAULT_LOG_PATH
    log_path.parent.mkdir(parents=True, exist_ok=True)
    row = { ... }
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
```

This keeps banner-emission and JSONL-emission as two outputs of the
same dispatch event, eliminating the "parse the banner string back"
dependency.

### 3.2 task_id / issue_number sourcing

The dispatcher does not currently know which task it is being run
under. Two options:

- **(a)** Read from a session-scoped env var the orchestrator sets
  before dispatching (`MAESTRO_CURRENT_TASK=T0.4`,
  `MAESTRO_CURRENT_ISSUE=22`). Lightweight; orchestrator
  responsibility.
- **(b)** Pass as keyword arguments through the MCP tool call.
  Heavier; requires schema changes to all four worker tools.

**Decision**: (a). The orchestrator already has the task ID in
context (it just opened the task issue at session start) and sets
the env var once per task. Workers stay schema-clean. If the env
var is unset, the row records `task_id=null` and is shown in a
"unattributed" footnote on the savings page.

### 3.3 Banner parity (T6.1)

Independent of JSONL emission, banners on librarian/reviewer/scribe
must reach shape parity with coder. This is its own sub-issue because
it has no dependency on the rest: even without JSONL, parity helps
human-visible orchestrator logs.

Banner shape (all four workers, identical):

    [<tool> dispatch — <model> — <wall>s — <total_tokens> tokens]

Placement differs by output format:

- `coder` emits plaintext (DeepSeek reasoning + code blocks). The
  banner is a plain string prefix on `result_text`, separated from
  the body by `\n\n`. Already implemented before T6.1.
- `librarian` / `reviewer` / `scribe` emit strict JSON. Prefixing a
  string before the JSON would break `json.loads()` for every
  consumer (including the orchestrator). For these three workers,
  the banner is embedded as a `_banner` field inside the JSON
  object. The validators already ignore extra fields per their
  "forward compatibility" docstrings, so no allowlist edit is
  needed. Error-path responses (`_error_response(...)`) intentionally
  omit `_banner` because their `usage` is null — a banner with
  `total_tokens=None` would lie. Coder's error path is symmetric.

Extraction rule (single helper, `extract_banner(result_text)` in
`bootstrap/maestro_server.py`):

    if result_text.startswith("["):
        return result_text.split("\n", 1)[0]   # plaintext-prefix case
    try:
        obj = json.loads(result_text)
    except (json.JSONDecodeError, ValueError):
        return None
    if isinstance(obj, dict):
        banner = obj.get("_banner")
        if isinstance(banner, str):
            return banner
    return None

Banner *shape* is identical across workers; *placement* follows
output type. coder's output is intentionally unstructured (the
orchestrator reads code, not JSON) while the other three are
intentionally JSON (validated, machine-consumable). T6.1 preserves
both contracts.

Banner construction itself goes through `_build_banner(tool, model,
duration, total_tokens)` so the format string lives in one place; if
the shape ever changes, the regex in `BANNER_REGEX` and the tests
in `tests/test_worker_banners.py` are the single migration surface.

## 4. Renderer

### 4.1 `scripts/render_savings.py` — top-level flow

```
1. Read dispatch-log.jsonl into rows (skip blanks + comments).
2. Group rows by task_id → per-task stats.
3. Group rows by tool → per-role stats.
4. Compute headline numbers.
5. Render Markdown via string templates.
6. Write to docs/savings.md atomically (write to .tmp + rename).
```

### 4.2 Determinism rules

- Sort row keys alphabetically when serializing (already enforced at
  emit time).
- Sort tasks by issue_number descending (stable, reproducible).
- Sort roles alphabetically.
- "Last updated" timestamp = max(started_at) across all rows, not
  `datetime.now()`.
- Float formatting: 2 decimal places for $; 1 decimal for percentages;
  integer for tokens and wall seconds.

### 4.3 Provider rates table (versioned)

Embedded in the renderer as a versioned constant; methodology page
explains why rates are baked in (so historical pages remain
reproducible if rates change). Rate-table updates happen as
explicit code changes, not silent.

```python
PROVIDER_RATES_USD_PER_M_TOKENS = {
    # snapshot 2026-05-09; updates require explicit PR
    "claude-opus-4-7": {"input": 15.0, "output": 75.0},
    "deepseek-v4-pro": {"input": 0.27, "output": 1.10},
    "deepseek-v4-flash": {"input": 0.07, "output": 0.27},
}
```

When `prompt_tokens` and `completion_tokens` are both null and only
`total_tokens` is known, the renderer uses a 50/50 split as the
neutral assumption and footnotes this.

## 5. Methodology page (`docs/savings-methodology.md`)

Sections:

1. **What "measured" means** — fields sourced directly from worker
   API responses, captured at dispatch time, never recomputed.
2. **What "estimated" means** — Opus baseline formula, the 50/50
   prompt/completion split when only total is known, the
   banner-gap-era backfills.
3. **Opus baseline formula** — `opus_$ = (tokens × opus_rate)`,
   labelled as a **lower bound** because Opus would typically use
   *more* tokens than the worker for the same task (not fewer); the
   real savings ratio is therefore at least the reported one.
4. **Provider rates** — table with sources, link to provider
   pricing pages, snapshot date.
5. **Gaps** — what is *not* measured: orchestrator-side Opus
   consumption, cache hit ratios, prompt-engineering iteration
   cost. Each named explicitly so reposted versions of the page
   carry the caveats.
6. **Reproducibility** — "Run `python scripts/render_savings.py`
   against the committed JSONL; output should match the committed
   `docs/savings.md` byte-for-byte. CI may enforce this in v0.0.4."
7. **How to disable telemetry** — `MAESTRO_DISPATCH_LOG=""`.
8. **Honesty key** — symbol legend (✓ measured, ⚠ estimated, ◇
   computed, — unavailable).

## 6. Failure modes

- **Malformed JSONL row** → renderer logs a warning to stderr and
  skips the row; never fails. The dispatch path that wrote it
  emitted a banner anyway, so visibility is preserved.
- **Unknown model in rates table** → row marked ⚠ "rate-unknown"
  in the page; aggregates exclude it.
- **`MAESTRO_DISPATCH_LOG` points to unwritable path** → the dispatch
  handler logs a warning and continues without writing. Telemetry
  failure must never break a worker dispatch.
- **Banner-gap regression** (a worker stops emitting tokens again) →
  rows from that worker show `total_tokens=null` for that period,
  rendered as ⚠. Renderer keeps producing a page; the regression is
  visible.
- **Concurrent dispatches** → JSONL append is line-atomic on POSIX
  for writes < PIPE_BUF; rows are small (< 500 bytes) so we are
  inside that bound. Lock is unnecessary at current scale.

## 7. Affected modules

- New: `docs/data/dispatch-log.jsonl` — committed audit trail.
- New: `scripts/render_savings.py` — JSONL → Markdown renderer.
- New: `scripts/begin_task.sh` — sets `MAESTRO_CURRENT_TASK` / `MAESTRO_CURRENT_ISSUE` env vars for the current shell (sourced, not executed). Companion helper landing alongside T6.2.
- New: `docs/savings.md` — generated, committed.
- New: `docs/savings-methodology.md` — hand-written methodology.
- Modified: `bootstrap/maestro_server.py` —
  - T6.1: banner parity for librarian / reviewer / scribe.
  - T6.2: `_emit_dispatch_row` helper, called from each dispatch wrapper.
- Modified: `README.md` — one-line link to `docs/savings.md`
  (separate sub-issue per H3 protected-doc rule).
- Modified (orchestrator behavior, no code change): the orchestrator
  sets `MAESTRO_CURRENT_TASK` and `MAESTRO_CURRENT_ISSUE` env vars
  at the start of each task. Documented in `CLAUDE.md` updates? —
  open question, see §8.

## 8. Resolved open questions (2026-05-10)

User delegated all three; resolutions baked in:

1. **task_id / issue_number sourcing** — go with the `scripts/begin_task.sh T<id>`
   helper command rather than a CLAUDE.md behavioral mandate. The helper
   exports `MAESTRO_CURRENT_TASK` and `MAESTRO_CURRENT_ISSUE` for the
   current shell. CLAUDE.md gains one short reference pointing at the
   helper, not a hard mandate. Lighter, recoverable when humans run
   workers directly. Implementation lives alongside T6.2.

2. **T6.6 (README link) timing** — do it **right after T6.3** lands the
   first rendered `docs/savings.md`, not at the end of the epic. Lets
   the public link be live as backfill (T6.5) and forward measurement
   (T6.7) accumulate, rather than dark until the very end. Sub-task
   ordering updated accordingly: T6.1 → T6.2 → T6.3 → T6.6 → T6.4 →
   T6.5 → T6.7.

3. **CI verification of renderer determinism** — out of scope for
   v0.0.3. Will be filed as a follow-up issue after Epic 6 closes.
   Methodology page §6 already states the contributor invariant ("run
   the renderer; output should match committed file byte-for-byte"),
   so the discipline holds even without CI enforcement.

## 9. ADR follow-up

ADR-0010 will record:
- Append-only JSONL as the storage format (vs per-task JSON files
  or live API).
- "Same token count × Opus rate" as the conservative Opus baseline
  formula (vs re-running tasks in Opus, vs not claiming savings).
- Provider rates baked into renderer code, not external file.

The ADR is small (~50 lines); written in T6.4 alongside the
methodology page so the two stay consistent.
