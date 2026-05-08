# Design: Epic 3 — team observability

**Issue**: #15
**Status**: draft

> Pass-1 draft. Establishes the three observability surfaces (dispatch log,
> execution flow, problem panel) and frames their dependencies on the MCP
> server. Log storage choice (JSONL vs SQLite), retention policy, and the
> precise instrumentation invasiveness are deferred to v0.0.3 design pass 2.

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

The Web UI gains three surfaces tied to dispatch activity:

### Dispatch log (history)

A reverse-chronological list of every `cheap_code_gen` invocation (and
future workers, when they exist). Each entry shows: timestamp, role
that handled it, member alias, model used, brief input summary, brief
output summary, success / failure, duration, optional cost.

Clicking an entry expands to full input and full output (truncation rules
TBD in pass 2 — payloads can be large).

### Execution flow (live)

While a Claude Code session is running and dispatching to Maestro, the
Web UI shows a live view: which member is currently executing, ordered
by dispatch time, with state (queued / running / done / failed). New
invocations appear; running ones tick their elapsed time; completed ones
move to the history.

The live view does not require the Web UI to know about Claude Code — it
reads the same dispatch log file, tailing newest entries.

### Problem panel

A dedicated tab listing entries that need human attention:

- Failed invocations.
- Invocations the worker explicitly returned a "blocked / need human
  input" status for (this is a v0.0.3 contract addition — see Technical
  design).
- Configuration warnings surfaced from earlier (e.g., Epic 1's "config
  missing, fell back to v0.0.2 defaults").

Items in the problem panel can be dismissed (acknowledged) or kept open.

## Technical design

### Where the dispatch log lives

A file (or files) on the filesystem at a path defined by Epic 0's shared
paths module. The Web UI tails it for the live view; reads it for the
history view.

Storage format candidates, decided in pass 2:

- **JSONL.** One line per invocation. Append-only, human-readable, simple
  to tail. Reading old entries means scanning the file.
- **SQLite.** Indexed reads, easy filtering, slightly more complex to
  write atomically and tail.

Trade-off: JSONL is friendlier to the "tail with file watcher" live-view
implementation; SQLite is friendlier to the history view's filtering and
search. Pass-2 ADR.

### What gets logged — the contract

Every dispatch from MCP server side emits an event when:

- Invocation **starts** (request_id, role, model, input summary, started_at).
- Invocation **ends** (request_id, success/failure, output summary,
  finished_at, optional cost / token counts, optional error).
- Invocation reports **blocked / need human input** (request_id, blocking
  reason, what's needed).

The "need human input" event type is new in v0.0.3 — workers don't emit it
today. Whether `cheap_code_gen` itself learns to emit it depends on
whether v0.0.3 changes the worker's behavior. Decision deferred to pass 2.
Worst case: v0.0.3 ships without the blocked event type and the problem
panel only shows failures and config warnings — the panel still earns its
keep.

### MCP server instrumentation

The MCP server must write dispatch events to the log location. This is
the actual change to the MCP runtime in Epic 3. Two design dimensions
deferred to pass 2:

- **Invasiveness.** Wrap each tool function with a decorator? Add an
  explicit log call inside each tool? A shared dispatcher that all tools
  go through? The wrap-with-decorator approach keeps tool code clean;
  the explicit-call approach is more obvious in code. Pass-2 decision.
- **Failure mode of logging itself.** If the log can't be written
  (permissions, disk full), what happens to the dispatch? The principle
  is: dispatch must not fail because logging failed. Log to stderr as a
  fallback and continue. Pass-2 spec.

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

High-level milestones.

- [ ] T3.1 — Pass-2 design: log storage format ADR (JSONL vs SQLite)
- [ ] T3.2 — Pass-2 design: instrumentation invasiveness decision
- [ ] T3.3 — Pass-2 design: retention policy default
- [ ] T3.4 — Pass-2 design: whether v0.0.3 ships the blocked-event type
- [ ] T3.5 — Implement: log writer in MCP server
- [ ] T3.6 — Implement: log reader + tailer in Web UI
- [ ] T3.7 — Implement: history view
- [ ] T3.8 — Implement: live execution-flow view
- [ ] T3.9 — Implement: problem panel (failures + config warnings; blocked events conditional on T3.4)
- [ ] T3.10 — Verify: a Claude Code session that dispatches `cheap_code_gen` is visible in real time in the Web UI; history persists across Web UI restarts; failures show in the problem panel.

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

- **OPEN-3.1.** Log storage: JSONL vs SQLite. Pass-2 ADR. Couples to
  the live-tail implementation difficulty.
- **OPEN-3.2.** Retention policy default. Rotate-by-age, rotate-by-count,
  rotate-by-size, or no rotation? Pass-2 decision.
- **OPEN-3.3.** Instrumentation invasiveness — decorator wrapping vs
  explicit log calls vs shared dispatcher. Pass-2 decision; affects how
  much MCP server code changes.
- **OPEN-3.4.** Whether v0.0.3 introduces a "blocked / need human input"
  event type and whether `cheap_code_gen` learns to emit it. If yes,
  worker code changes; if no, problem panel ships without that capability
  in v0.0.3.
- **OPEN-3.5.** Truncation rules for large input/output payloads in the
  history view. Pass-2 UX call.
- **OPEN-3.6.** Cost / token-count display. v0.0.2 doesn't track cost. If
  Epic 3 introduces it, even minimally, that's a small new responsibility
  on the MCP server side. Pass-2 scope decision.
- **OPEN-3.7.** Concurrency: two MCP server processes writing the same
  log. Atomicity guarantees needed for the chosen format. Pass-2 spec.
