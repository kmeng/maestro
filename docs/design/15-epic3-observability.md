# Design: Epic 3 — team observability

**Issue**: #15
**Status**: approved

> Approved after pass-2 (D1–D5, 2026-05-08). Log format and schema,
> instrumentation pattern, retention/truncation/cost, and UI surfaces
> are all resolved. Implementation tasks T3.1–T3.10 below are PR-sized
> closed loops, ready to land in order against `v0.0.3` after Epic 0
> T0.1/T0.3/T0.4 and Epic 1 T1.1/T1.2/T1.6 land first.
>
> ADR produced: [0007](../adr/0007-dispatch-log-format-and-schema.md).

## Problem

When Maestro dispatches a task to `cheap_code_gen` (or future workers),
the user has no visibility into what was sent, what came back, or where
things went wrong. Today the only signal is "Claude Code mentioned it
called the tool" — buried in transcript, no structure. For Maestro to be
trustworthy as a coordination layer, the user needs to see:

- **What happened.** A historical log of every dispatch.
- **What's happening.** A live execution-flow view during a Claude Code
  session.
- **What needs my attention.** A problem panel surfacing failures, blocked
  invocations, and human-in-the-loop questions.

Epic 3 is also the v0.0.3 epic that delivers on the dogfooding promise of
v0.0.2: until Maestro itself routinely uses `cheap_code_gen` and the user
can see it doing so, the whole project remains a thesis rather than a
demonstration.

## Out of scope

- Long-term analytics. Per-invocation token cost may be displayed; trend
  analysis, cost-over-time charts, and budget alerts are post-v0.0.3.
- Multi-project log aggregation. Each project has its own dispatch log.
  Cross-project view is post-v0.0.3.
- External observability integration (sending events to OpenTelemetry,
  Datadog, etc.). v0.0.3 is local-only.
- Editing or replaying past dispatches from the UI. Read-only history in
  v0.0.3.
- Structured rerun / retry orchestration. The problem panel surfaces that
  something failed; the user resolves it via Claude Code, not via the
  Web UI.

## Functional design

The Web UI gains three surfaces tied to dispatch activity. All three
read the same `dispatch.jsonl` — no state duplication. UX decided in
pass-2 D4.

### Surface 1 — History view (passive)

Reverse-chronological list of dispatches. Each row folds a
`request_id`'s events into a single line:

| Column | Value |
|---|---|
| Status | ✓ success / ✗ failed / ⊘ refused / ⤴ fallback-used |
| Time | "14:23:11" — full timestamp on hover |
| Role + member | "Junior — Jamie" |
| Model | `deepseek-coder` |
| Duration | "1.4s" |
| Cost (optional) | "230→1420 tok" — "—" if absent |
| Summary | First 60 chars of `input_summary` |

Drill-down on click: full `input_summary`, `output_summary` (with a
"(truncated)" note if the log entry was capped per D3),
`error_message` if failed, validation details if refused.

**Source**: one-shot read of current `dispatch.jsonl` on page load;
events folded by `request_id` into rows. No tail.

**v0.0.3 reads only the current file.** Rotated files (`dispatch.<ts>.jsonl`)
exist on disk but aren't loaded; manual access only. Pass-3
enhancement: scroll-back loads older files.

### Surface 2 — Live execution flow (active)

Two zones:

- **Running** — dispatches with `dispatch.start` but no terminal
  event yet. Each card shows role/member/model + elapsed time
  (ticks once per second).
- **Completed (recent)** — last ~10 dispatches with terminal events.
  Auto-scrolls into the history view as the user navigates away.

**Source**: SSE-tailed `dispatch.jsonl`. The Web UI subscribes via
htmx's `hx-sse` ([ADR-0002](../adr/0002-frontend-no-build-htmx.md)).
FastAPI serves the stream via `EventSourceResponse`
([ADR-0001](../adr/0001-web-framework-fastapi.md)).

Per-event UI behavior:

- `dispatch.start` → render new card in **Running**.
- `dispatch.end` / `dispatch.failed` → move card from Running to
  Completed.
- `dispatch.fallback.config_absent` → annotate the corresponding
  `request_id`'s card with a "↩ fell back" badge.
- `dispatch.refused.config_invalid` → render directly in Completed
  as a refused row (no Running phase).

**Reconnect**: SSE event IDs are `(file_inode, byte_offset)`. The
client reconnects with `Last-Event-ID`; the server resumes from the
recorded offset. If the file inode has changed (rotation), the
server reopens; the client receives a synthetic "rotated" marker
and clears any open-Running state for events older than the new
file.

### Surface 3 — Problem panel

Dedicated tab listing items that need user attention. Three
categories:

| Category | Source events | Per-row content |
|---|---|---|
| Failed dispatches | `dispatch.failed` | timestamp, role, `error_kind`, `error_message` |
| Config refusals | `dispatch.refused.config_invalid` | timestamp, validation field, message, **CTA** "Open team config to fix" → routes to Epic 1's role-catalog view |
| Config fallbacks | `dispatch.fallback.config_absent` | grouped: "N dispatches used the v0.0.2 fallback model. Configure your team to use the model you want." **CTA** "Configure team" → opens Epic 1's wizard |

**Dismissal**: per-browser-session only — clicking acknowledge fades
the row but doesn't persist. v0.0.3 does not write dismissal state
back to disk. (Persisting would require a sidecar file; the cost
isn't justified for a UX nicety in v0.0.3.)

**Empty state**: a Chinese reassurance message; shown when zero items
across all three categories.

### State derivation, not duplication

The Web UI maintains no separate "current state" database. Each view
derives from the log on demand:

- History view → one-shot scan of current `dispatch.jsonl`.
- Live view → SSE-subscribed tail of the same file.
- Problem panel → filtered scan of the same file (failed + refused +
  fallback events only).

A user opening the Web UI cold immediately sees: live view empty (no
in-flight dispatches), history populated from past sessions, problem
panel populated from past problems.

### Performance budget

- History view full scan: 5 MB worst case (D3 rotation cap),
  sub-100 ms in Python.
- SSE event delivery: events surface within ~1 s of MCP-server emit
  (1 Hz `os.stat` polling on the file in v0.0.3). Inotify/kqueue is
  pass-3.
- Problem-panel filter: linear scan, identical to history.

### Language (D6 cross-cutting)

- All UI labels (column headers, badges, CTA buttons, empty-state
  messages) in **Chinese**.
- Event payload content (`input_summary`, `output_summary`,
  `error_message`, etc.) rendered **verbatim**. The user's prompt
  may itself be any language; Maestro doesn't translate it.
- `event_type` strings are machine identifiers, never shown to the
  user — the UI uses Chinese labels mapped from event types.

## Technical design

### Log format and schema — decided

Pass-2 D1 settles format, schema, and concurrency. Full rationale in
[ADR-0007](../adr/0007-dispatch-log-format-and-schema.md).

#### Format

**JSONL** at `<project-root>/.maestro/logs/dispatch.jsonl`. One JSON
object per line, terminated by `\n`. Append-only; rotation via file
replacement (D3).

Path comes from [ADR-0003](../adr/0003-shared-state-file-layout.md)'s
`paths.dispatch_log_path(project_root)`.

#### Common fields on every event

```json
{
  "event_type": "dispatch.start",
  "event_version": 1,
  "request_id": "01HXNZ7K0K3M7VHV6E5G6X4XYA",
  "timestamp": "2026-05-08T14:23:11.123Z"
}
```

`event_version` is per event type — adding fields to one type doesn't
force a global schema bump.

#### Five event types in v0.0.3

| Type | Role in flow | Type-specific fields |
|---|---|---|
| `dispatch.fallback.config_absent` | Pre-start informational (Epic 1 D4) | `role`, `fallback_model` |
| `dispatch.refused.config_invalid` | Terminal alone — no `start`/`end` follow (Epic 1 D4) | `validation_error_field`, `validation_error_message` |
| `dispatch.start` | Worker invocation begins | `role`, `model`, `member`, `input_summary` |
| `dispatch.end` | Worker invocation succeeds | `output_summary`, `duration_ms`, optional `cost` |
| `dispatch.failed` | Worker invocation fails | `duration_ms`, `error_kind`, `error_message` |

`dispatch.blocked` is **deferred** (OPEN-3.4) — re-open when richer
workers arrive in v0.0.4+.

#### In-code contract

Pydantic discriminated union on `event_type`. Models live in
`maestro/dispatch_log/events.py`. MCP server emits via
`event.model_dump_json()`; Web UI parses via the same models. Same
discipline as `team.yaml` ([ADR-0004](../adr/0004-team-config-format-and-schema.md)).

#### Per-event size cap

**4 KB** per serialized line (including the trailing `\n`). What makes
the concurrency guarantee below hold. D3 settles truncation rules to
enforce.

#### Concurrency

Two MCP server processes (e.g., user with two Claude Code sessions on
the same project) may both append concurrently. POSIX `O_APPEND` plus
single `write()` calls under `PIPE_BUF` (≥ 512, typically 4096) is
atomic — the kernel never interleaves partial writes.

```python
fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
os.write(fd, line.encode("utf-8") + b"\n")
```

One `os.write()` per event. Combined with the 4 KB size cap, two
concurrent writers cannot tear each other.

Windows note: `O_APPEND` atomicity guarantees on Windows differ from
POSIX. v0.0.3 ships Linux/macOS-correct; Windows users either run WSL
or accept best-effort atomicity (single-user reality is fine; the
worst case is one corrupt log line, which the reader detects via parse
failure → log warning → skip).

Reader side (Web UI): single-process, multiple browser tabs share one
tail-reader. Track last-read offset and inode; on poll, if `os.stat`
shows new bytes, parse from the offset; on inode change, reopen and
reset.

### Retention, truncation, cost

Pass-2 D3 settles three reversible knobs that ride on top of the
format contract from D1.

#### Truncation

Per-field caps that keep the serialized line under D1's 4 KB ceiling:

| Field | Lives in | Cap |
|---|---|---|
| `input_summary` | `dispatch.start` | 1 KB |
| `output_summary` | `dispatch.end` | 1 KB |
| `error_message` | `dispatch.failed` | 512 B |
| `validation_error_message` | `dispatch.refused.config_invalid` | 512 B |

Worst-case event size with all caps hit: ~1.8 KB. Comfortable headroom
under the 4 KB ceiling.

**Algorithm**: head + tail with ellipsis marker. For an over-cap
string of length `N` and cap `C`:
- `N ≤ C` → keep as-is.
- `N > C` → `(C-32)/2` leading bytes + `…<truncated N→C bytes>…` +
  `(C-32)/2` trailing bytes.

Head + tail (rather than head-only) preserves both the meaningful
opening and the meaningful closing of LLM responses and error
messages.

UTF-8 boundary-safe: truncation respects character boundaries via
`bytes.decode("utf-8", errors="ignore")` after byte slicing.

The full payload still flows to Claude Code at dispatch time —
truncation is a *logging* concern, not a *dispatch* concern.

#### Rotation: by size, 5 MB

When `os.stat(dispatch.jsonl).st_size > 5 * 1024 * 1024`, the
dispatcher rotates before its next write:

1. Rename `dispatch.jsonl` → `dispatch.<timestamp>.jsonl` (timestamp
   ISO-8601 compact, e.g. `dispatch.20260508T142311Z.jsonl`).
2. Open a fresh empty `dispatch.jsonl`.

Check runs inside `emit_event` before each write. With the 4 KB
per-event cap, 5 MB ≈ ~1300 events worst case (typically far more —
events average well below the cap).

**No auto-deletion in v0.0.3.** Rotated files accumulate. Users may
want them; deleting without consent is risky. Disk pressure → users
delete manually. If demand surfaces post-v0.0.3, an auto-prune
setting can ship.

**Web UI v0.0.3 reads only the current `dispatch.jsonl`.** Older
rotated files exist on disk but aren't loaded into the history view.
Pass-3 nice-to-have: scroll-back loads older files on demand.

**Reader response to rotation**: when the Web UI's tail-reader sees
the inode of `dispatch.jsonl` change, it reopens and resets offset.
Already specified in D1.

#### Cost / token display

`dispatch.end` carries an optional `cost` object:

```json
{
  "cost": {
    "prompt_tokens": 230,
    "completion_tokens": 1420
  }
}
```

v0.0.3 records token counts when the provider returns them
(DeepSeek, Anthropic, etc.). **No USD computation in v0.0.3** —
USD requires per-model pricing tables, currency-rate concerns, and
list-price-vs-actual ambiguity. Defer.

When the executor doesn't return token info (some providers, some
error paths), `cost` is omitted entirely from `dispatch.end`. The
Web UI shows "—" for those rows; no error or warning.

### MCP server instrumentation — shared dispatcher

Pass-2 D2 settles the instrumentation pattern.

#### Shape

Every MCP tool that worker-dispatches goes through one shared
function: `dispatcher.run()`. The MCP tool itself stays thin:

```python
def cheap_code_gen(prompt: str) -> str:
    return dispatcher.run(
        role=RoleId.JUNIOR,
        input=prompt,
        executor=lambda model: call_model(model, prompt),
    )
```

`dispatcher.run()` owns the full dispatch lifecycle:

1. Generate `request_id` (ULID for sortability).
2. Resolve the model for the role per
   [Epic 1 D4](13-epic1-team-composition.md#failure-modes-file-level----mcp-server-fallback-semantics):
   - `team.yaml` absent → emit `dispatch.fallback.config_absent`,
     use v0.0.2 default model
   - `team.yaml` invalid → emit `dispatch.refused.config_invalid`,
     return structured error to Claude Code, no further events
   - valid → use `roles.<role>.model`
3. Emit `dispatch.start` with the resolved model.
4. Call the executor lambda.
5. On success: emit `dispatch.end`. On exception: emit
   `dispatch.failed`.
6. Return the result (or structured error if refused).

Why a shared dispatcher rather than per-tool decorators or
inline-explicit logging:

- **Consistency by construction.** Every dispatch passes through one
  function. Forgetting to emit an event becomes structurally
  impossible. Inconsistent `input_summary` formatting becomes
  impossible.
- **Epic 1 D4's fallback/refuse logic naturally lives here** — the
  dispatcher knows the role, knows the model, knows when to fall
  back. Per-tool implementation would duplicate that logic.
- **Extensible.** Future tools (post-v0.0.3) plug in with three
  lines: tool wrapper, role binding, executor lambda.
- **Testable.** The dispatcher is one unit, tested once. Tools become
  test-light.

#### Logging failure must not fail dispatch

If the log file is unwritable (permissions, disk full, parent
directory gone), `emit_event` logs to stderr and returns:

```python
def emit_event(event: DispatchEvent) -> None:
    line = event.model_dump_json() + "\n"
    line = _truncate_if_oversize(line)  # D3 truncation rules
    try:
        with open(log_path, "ab") as f:
            f.write(line.encode())
    except OSError as e:
        sys.stderr.write(f"maestro: dispatch log write failed: {e}\n")
```

The dispatch returns its real result to Claude Code as if logging
hadn't happened. Observability degrades gracefully — the user sees
nothing in the Web UI for that dispatch but `cheap_code_gen` still
worked. Stderr surfaces the error to whoever is watching the MCP
server's log.

Pass-3 nice-to-have (not v0.0.3): the Web UI detects "log file
present but has gaps" and surfaces it. v0.0.3 ships without that.

#### Module layout

- `maestro/dispatch_log/` — Pydantic event models (D1), the writer
  (`emit_event`), the reader/tail logic (consumed by the Web UI).
- `maestro/dispatcher.py` — `dispatcher.run()`. Imports from
  `dispatch_log` and from `team` (Epic 1's models for the
  `team.yaml` resolution).
- `maestro/server.py` — existing MCP entry point. `cheap_code_gen`
  becomes a thin wrapper that delegates to `dispatcher.run()`. Other
  tools added in future releases follow the same pattern.

### Event correlation

Each dispatch has a `request_id` (UUID or similar) so the start, end, and
any block events can be correlated. The Web UI's live-view tracks
request_ids to move entries between "running" and "done."

### Affected modules

- New: `maestro/dispatch_log/` (or similar) — the log writer (used by MCP
  server) and the log reader (used by Web UI).
- Existing: MCP server tool implementations — instrumented to write
  dispatch events. Minimal interface change for tools, real behavior
  change in the runtime.
- New: Web UI screens for history, live flow, problem panel.
- New: HTTP API endpoints for tail-style streaming (e.g., server-sent
  events) to the live view.

### Failure modes

- **Log file unwritable.** MCP server logs to stderr and continues.
  Dispatch still works; the Web UI shows a missing-events warning.
- **Log file grows unbounded.** Pass-2 retention policy. Candidates:
  rotate by size, rotate by age, rotate by entry count, never rotate
  (user manages). Likely pass-2 default: rotate by entry count or age.
- **Live view subscriber drops.** Reconnect-and-rewind by request_id.
- **Two MCP server processes running concurrently** (e.g., user has
  two Claude Code sessions open against the same project). Both write
  to the same log. Pass-2: ensure writes are atomic (line-level for
  JSONL, transactional for SQLite). Concurrency is real.

## Task breakdown

PR-sized closed loops. **Prerequisites**: Epic 0 T0.1 (paths), T0.3
(FastAPI), T0.4 (empty-shell page); Epic 1 T1.1 (Pydantic models with
`RoleId`), T1.2 (config loader), T1.6 (initial inline model
resolution). T3.5 then replaces T1.6's inline implementation with
the dispatcher.

- [ ] **T3.1** — Pydantic event models in `maestro/dispatch_log/events.py` per [ADR-0007](../adr/0007-dispatch-log-format-and-schema.md) (discriminated union on `event_type`). Unit tests on round-trip + serialized-line ≤ 4 KB after truncation. (~1.5h)
- [ ] **T3.2** — `emit_event` writer in `maestro/dispatch_log/writer.py`: serialize, truncate per D3, append via `os.open`+`os.write`, OSError → stderr fallback. Rotation: size check before write, rename + reopen at 5 MB. No-op import from MCP server startup so the module is exercised. (~2h)
- [ ] **T3.3** — Reader in `maestro/dispatch_log/reader.py`: one-shot file scan + tail-mode generator. `(inode, offset)` tracking; reopens on inode change. (~1.5h)
- [ ] **T3.4** — `dispatcher.run(role, input, executor)` in `maestro/dispatcher.py`: ULID `request_id`, model resolution per [Epic 1 D4](13-epic1-team-composition.md#failure-modes-file-level----mcp-server-fallback-semantics), event flow, exception → `dispatch.failed`. (~1.5h)
- [ ] **T3.5** — Refactor `cheap_code_gen` in `maestro/server.py` to a thin wrapper over `dispatcher.run()`. Replaces Epic 1 T1.6's inline implementation. v0.0.2 fallback behavior preserved exactly. (~1h)
- [ ] **T3.6** — SSE endpoint `GET /api/dispatch_log/stream` in the Web UI: FastAPI `EventSourceResponse` wrapping the tail-reader. `Last-Event-ID` resume with `(inode, offset)` keys. (~1h)
- [ ] **T3.7** — History view UI: scan + fold-by-`request_id`, drill-down on click. Chinese labels per D6. (~1.5h)
- [ ] **T3.8** — Live view UI: htmx `hx-sse`, Running/Completed zones, elapsed-time tick, badge annotations from `fallback.config_absent` events. Chinese labels. (~2h)
- [ ] **T3.9** — Problem panel UI: filtered view, three categories (failed / refused / grouped fallback), CTAs to team config and wizard. Per-session dismissal. Chinese labels + empty state. (~1.5h)
- [ ] **T3.10** — End-to-end verification PR. Documented manual smoke covering all three surfaces, plus the v0.0.2 regression check. (~1.5h)

T3.7/T3.8/T3.9 can land in any order among themselves (independent
UI surfaces sharing the same backend).

## Acceptance criteria

- A `cheap_code_gen` invocation produces visible dispatch log entries:
  start, end (success or failure).
- The history view in the Web UI shows past invocations in
  reverse-chronological order with the documented fields.
- The live execution-flow view updates while a Claude Code session is
  running, without manual refresh.
- A failed invocation appears in the problem panel with enough info for
  the user to know what failed.
- Logging failures (e.g., disk full) do not break dispatch — the
  invocation still returns its result to Claude Code.
- The MCP `cheap_code_gen` interface as seen by Claude Code is unchanged.
  Instrumentation is internal.

## Open questions

- ~~**OPEN-3.1.** Log storage: JSONL vs SQLite.~~ **Resolved**: JSONL at `<project-root>/.maestro/logs/dispatch.jsonl`, append-only, line-level atomic via `O_APPEND`. See [ADR-0007](../adr/0007-dispatch-log-format-and-schema.md).
- ~~**OPEN-3.2.** Retention policy default.~~ **Resolved**: rotate by size at 5 MB. Rotated files accumulate (no auto-deletion in v0.0.3). Web UI reads current file only; older-file scroll-back is post-v0.0.3.
- ~~**OPEN-3.3.** Instrumentation invasiveness.~~ **Resolved**: shared dispatcher (`dispatcher.run()`). MCP tools become thin wrappers; the dispatcher owns request-id generation, model resolution per Epic 1 D4, event emission, and failure handling. Logging failure does not fail dispatch — `emit_event` falls back to stderr. Detail in the "MCP server instrumentation" subsection.
- ~~**OPEN-3.4.** Whether v0.0.3 introduces a "blocked / need human input" event type.~~ **Resolved**: deferred to v0.0.4+. v0.0.3's worker is the unchanged v0.0.2 `cheap_code_gen`; shipping the event type would require worker behavior change. Re-trigger: any richer worker that supports human-in-the-loop signaling. See [ADR-0007](../adr/0007-dispatch-log-format-and-schema.md).
- ~~**OPEN-3.5.** Truncation rules.~~ **Resolved**: per-field byte caps (1 KB / 1 KB / 512 B / 512 B), head + tail with ellipsis marker, UTF-8-boundary-safe. The full payload still flows to Claude Code at dispatch time; only the log entry is truncated.
- ~~**OPEN-3.6.** Cost / token-count display.~~ **Resolved**: optional `cost` object on `dispatch.end` carries `prompt_tokens` and `completion_tokens` when the provider returns them. No USD computation in v0.0.3. Missing cost shows as "—" in the UI.
- ~~**OPEN-3.7.** Concurrency.~~ **Resolved**: POSIX `O_APPEND` + single `write()` ≤ `PIPE_BUF` is atomic across processes; 4 KB per-event cap (D3 truncation enforces) makes the guarantee hold. Windows is best-effort, documented. See [ADR-0007](../adr/0007-dispatch-log-format-and-schema.md).
- ~~**OPEN-3.8.** Two new dispatch-log event types from Epic 1 D4.~~ **Resolved**: `dispatch.fallback.config_absent` and `dispatch.refused.config_invalid` are both first-class in the schema. See [ADR-0007](../adr/0007-dispatch-log-format-and-schema.md).
