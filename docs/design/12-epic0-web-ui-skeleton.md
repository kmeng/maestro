# Design: Epic 0 — local Web UI skeleton

**Issue**: #12
**Status**: draft

> Pass-1 draft. Establishes the process model and the shape of the
> shared-state contract. Tech-stack choices, port-conflict strategy, and the
> precise file layout are deferred to v0.0.3 design pass 2 — almost certainly
> the first ADR trigger of v0.0.3.

## Problem

Today Maestro runs only as an stdio MCP server: there is no HTTP surface, no
browser-renderable view, no place to put a configuration wizard or an
observability dashboard. Epics 1–3 each need a Web UI to be useful, and they
all need it to behave consistently — same launch model, same way of finding
config, same way of finding dispatch logs.

Epic 0 is the foundation those epics stand on. It produces an empty-shell
Web UI on localhost and pins down the process model and the shared-state
contract. After Epic 0 lands, Epics 1, 2, and 3 are about content and
behavior — not about plumbing.

## Out of scope

- Any actual UI feature. The Web UI in Epic 0 is intentionally an empty
  shell — a navigation skeleton at most. Real screens are Epics 1–3.
- Authentication, login, multi-user. Maestro is single-user local.
- Remote / hosted deployment. Localhost only.
- Direct IPC between the Web UI process and the MCP server. They share
  state via the filesystem in v0.0.3. Direct IPC may come later.
- Auto-launching the Web UI when Claude Code starts. The user launches the
  Web UI explicitly. Auto-launch belongs to Epic 4 (packaging / launcher).

## Functional design

The user starts Maestro's Web UI with a single command (or, post-Epic-4, a
double-click). A localhost URL becomes available. Opening it in a browser
shows an empty Maestro-branded shell — a header, a placeholder navigation
area, a "you haven't done anything yet" body. None of the real flows
(team composition, project scaffolding, observability) are wired up yet —
those land in subsequent epics.

In parallel, the user's existing way of using Maestro keeps working: Claude
Code launches the MCP server as a stdio subprocess (today's behavior),
`cheap_code_gen` is callable, nothing changes for an existing user who
hasn't opted into the Web UI.

## Technical design

### Process model

```
┌────────────────────────────────────────────────────────────────────┐
│                        User's machine                              │
│                                                                    │
│    ┌──────────────────────┐     filesystem    ┌────────────────┐   │
│    │ Web UI process       │  ←── config ──→   │ MCP server     │   │
│    │  - localhost HTTP    │                   │ (stdio subproc │   │
│    │  - long-lived        │  ←── log    ──→   │  of Claude     │   │
│    │  - user-launched     │                   │  Code)         │   │
│    └──────────────────────┘                   └────────────────┘   │
│             ↑                                          ↑           │
│             │ browser                                  │ stdio     │
│         user's browser                          Claude Code main   │
│                                                       session      │
└────────────────────────────────────────────────────────────────────┘
```

Two processes, never directly RPC-ing each other. They share state via the
filesystem. This is load-bearing:

- Claude Code expects to be the only thing talking to the MCP subprocess
  over stdio. We don't break that contract.
- The Web UI's lifecycle is independent of any Claude Code session. The
  user can configure Maestro before Claude Code is running, and observe
  Maestro after a Claude Code session ends.

### Shared-state contract (skeleton)

Epic 0 defines that there is a shared-state contract; pass 2 picks the
exact shapes. The contract has two parts:

- **Config home** — where role/member/model bindings live. Read by both
  processes. Written primarily by the Web UI (Epic 1). Candidate locations
  to be evaluated in pass 2: `~/.maestro/`, project-local `.maestro/`, or a
  hybrid. The choice has implications for project portability and is one of
  Epic 1's open questions too.
- **Dispatch log location** — where the MCP server writes invocation
  events. Read by the Web UI (Epic 3). Candidate formats: JSONL file,
  SQLite. Decision lives in Epic 3.

Epic 0's pass-2 deliverable is a documented file layout and a tiny module
both processes import to find these paths. Epic 0 does **not** define the
log schema (that's Epic 3) or the config schema (that's Epic 1).

### HTTP server

A localhost HTTP server that:

- Binds to a stable preferred port. Falls back to a strategy TBD in pass 2
  when the port is taken.
- Serves the empty-shell Web UI as a single-page app, plus whatever
  bare-minimum API endpoints the shell needs (likely just a health check
  and a "what version of Maestro is this" endpoint).
- Runs in the foreground of the user-launched process. No daemonization in
  v0.0.3.

### Tech-stack choice

The Web UI process is Python.

- **Web framework: FastAPI**, served by uvicorn. Decided in pass 2; rationale
  in [ADR-0001](../adr/0001-web-framework-fastapi.md). FastAPI's native SSE
  primitives (via `sse-starlette`) and Pydantic-first design are the
  load-bearing reasons — they directly enable Epic 3's live view and remove
  schema duplication with the MCP SDK.
- **Frontend approach.** Pass-2 ADR (D2). Two camps under consideration:
  (a) plain HTML + a tiny progressive-enhancement JS layer, no build step;
  (b) a proper SPA framework. The first reduces install friction and
  dependency surface; the second scales better for Epic 3's live
  execution-flow view. To be decided next.

### Affected modules

- New: `maestro/webui/` (or similar) — the Web UI process entry point,
  HTTP server, frontend assets.
- New: a small `maestro/paths.py` (or similar) — the single source of
  truth for "where does config live, where does the dispatch log live."
  Imported by both the Web UI and the MCP server.
- Existing: `server.py` (MCP server entry point) — minimal change. May
  import the new paths module so it can find the dispatch log location
  (the actual dispatch logging instrumentation lives in Epic 3).
- Existing: `requirements.txt` — gains the chosen web framework.

### Failure modes

- **Port in use.** Pass-2 strategy. Candidates: pick the next free port and
  show it to the user; fail with a clear message and a `--port` override;
  bind to `:0` and write the chosen port into a discoverable file. Picking
  one is a pass-2 decision.
- **Browser not auto-opened.** Acceptable. Print the URL to the terminal.
  Auto-open is nice-to-have, not required.
- **Web UI process crashes.** MCP server keeps working. User restarts the
  Web UI when they need it.
- **MCP server crashes.** Web UI keeps running, shows last-known state from
  the dispatch log.

## Task breakdown

High-level milestones. Pass-2 of this design will split each into PR-sized
tasks.

- [ ] T0.1 — Pass-2 design: tech-stack ADR (web framework + frontend approach)
- [ ] T0.2 — Pass-2 design: shared-state file layout (config home path, dispatch log path)
- [ ] T0.3 — Implement: minimal HTTP server with empty-shell page, runnable via a single command
- [ ] T0.4 — Implement: shared paths module, imported (no-op) from MCP server entry point
- [ ] T0.5 — Implement: port-conflict fallback strategy
- [ ] T0.6 — Verify: MCP `cheap_code_gen` path is unchanged end-to-end

## Acceptance criteria

- Running a single command starts the Web UI process, prints a localhost
  URL, and the URL serves an empty-shell Maestro page in a browser.
- The Web UI process is independent of Claude Code: it runs whether or not
  a Claude Code session exists.
- The MCP server's `cheap_code_gen` invocation works identically to v0.0.2:
  same input, same output, no new required env vars beyond what v0.0.2
  required.
- A documented shared-paths module exists and is the single place either
  process consults for "where is config / where is the log."
- Port-in-use produces a clear, recoverable user experience (not a stack
  trace).

## Open questions

- ~~**OPEN-0.1.** Web framework choice (FastAPI vs Flask vs other). Pass-2 ADR.~~ **Resolved**: FastAPI + uvicorn — see [ADR-0001](../adr/0001-web-framework-fastapi.md).
- **OPEN-0.2.** Frontend approach (no-build progressive HTML vs proper
  SPA framework). Pass-2 ADR. Constraint: must support Epic 3's live
  execution-flow view without becoming a maintenance burden.
- **OPEN-0.3.** Port-conflict strategy. Pass-2 decision.
- **OPEN-0.4.** Where does config live — `~/.maestro/`, project-local
  `.maestro/`, or hybrid? Couples to Epic 1. Pass-2 decision, made jointly
  with Epic 1.
- **OPEN-0.5.** Single-process-mode for development convenience? It would
  be tempting to allow `python server.py` to also start the HTTP server in
  a thread, for ease of testing during development. Trade-off: convenience
  vs. enforcing the two-process discipline. Decide in pass 2.
- **OPEN-0.6.** Web UI auto-launch from a Claude Code session — explicitly
  out of scope here, belongs to Epic 4. Recorded so it isn't accidentally
  scope-creeped into Epic 0.
