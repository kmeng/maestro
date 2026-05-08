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

### Shared-state contract

The hybrid layout decided in [ADR-0003](../adr/0003-shared-state-file-layout.md):

```
~/.maestro/                             # user-global
├── credentials.env                     # API keys
├── projects.json                       # known project paths (recent-projects UI)
└── settings.yaml                       # user preferences

<project-root>/.maestro/                # project-local; in user's git repo
├── team.yaml                           # role→model bindings (Epic 1 schema)
├── logs/
│   └── dispatch.<format>               # dispatch log (Epic 3 format)
└── .gitignore                          # ships with: logs/
```

**Per-user state** lives in `~/.maestro/`: credentials, recent-projects
registry, user preferences. Never written into user projects.

**Per-project state** lives in `<project-root>/.maestro/`: `team.yaml`
is committed by default (team composition is a project decision); `logs/`
is gitignored via a scaffolding-supplied `.maestro/.gitignore`.

Both processes consume paths through a single `maestro/paths.py` module.
Code never hard-codes paths.

Epic 0 owns the path module and the directory creation. Epic 0 does **not**
define the schemas (`team.yaml` is Epic 1; dispatch log format is Epic 3).

### `.env` loader migration

v0.0.2's project-local `.env` loader (issue #6) is extended in v0.0.3 to
also check `~/.maestro/credentials.env`. Precedence (highest first):
process env → project `.env` → `~/.maestro/credentials.env`. v0.0.2
behavior is preserved at higher precedence — no regression for existing
users. Epic 0 ships the loader extension as a small task.

### HTTP server

A localhost HTTP server that:

- Binds to a stable preferred port. Default `19830`. The preferred port is
  user-configurable in `~/.maestro/settings.yaml`; transient overrides via
  a `--port` CLI flag.
- Serves the empty-shell Web UI as a single-page app, plus whatever
  bare-minimum API endpoints the shell needs (likely just a health check
  and a "what version of Maestro is this" endpoint).
- Runs in the foreground of the user-launched process. No daemonization in
  v0.0.3.

#### Port-conflict strategy

When the preferred port is already in use, scan upward through the next
**10** ports (preferred + 1 through preferred + 10). Bind to the first
free one. Print the chosen URL on stdout so the user can open it.

If all 11 ports in the scan window are taken, fail with a clear message
("ports `<preferred>`–`<preferred+10>` are all in use; pass `--port N` to
override") and exit. Pass-2 design call; reversible.

The preferred port persists across launches so a user's bookmark to
`http://localhost:19830` keeps working when nothing else has taken the
port. Auto-fallback runs only on collision; the URL stays stable in the
common case.

### Tech-stack choice

The Web UI process is Python.

- **Web framework: FastAPI**, served by uvicorn. Decided in pass 2; rationale
  in [ADR-0001](../adr/0001-web-framework-fastapi.md). FastAPI's native SSE
  primitives (via `sse-starlette`) and Pydantic-first design are the
  load-bearing reasons — they directly enable Epic 3's live view and remove
  schema duplication with the MCP SDK.
- **Frontend: no-build HTML with htmx + optional Alpine.js**, vendored as
  static assets. Decided in pass 2; rationale in
  [ADR-0002](../adr/0002-frontend-no-build-htmx.md). FastAPI returns HTML
  fragments; htmx handles AJAX and SSE→DOM swaps declaratively. No
  Node.js, no build step, no `node_modules`. SPA frameworks were rejected
  because the UI surface (forms + a live list) doesn't earn their cost
  and they would force a Node toolchain into Maestro's distribution.

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

- **Port in use.** Auto-fallback: scan +1 through +10 from preferred,
  bind to the first free, print the chosen URL. If all 11 ports are
  taken, fail with the `--port` override hint. See the "Port-conflict
  strategy" subsection above.
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
- ~~**OPEN-0.2.** Frontend approach (no-build progressive HTML vs proper SPA framework).~~ **Resolved**: no-build HTML + htmx (+ optional Alpine.js), vendored — see [ADR-0002](../adr/0002-frontend-no-build-htmx.md).
- ~~**OPEN-0.3.** Port-conflict strategy.~~ **Resolved**: default port `19830`; on conflict, scan +1 through +10 and bind to the first free; if all 11 are taken, fail with a clear error and the `--port` override hint. Persisted preferred port in `~/.maestro/settings.yaml`. Detail in the "Port-conflict strategy" subsection above.
- ~~**OPEN-0.4.** Where does config live — `~/.maestro/`, project-local `.maestro/`, or hybrid?~~ **Resolved**: hybrid (project-primary, user-secondary) — see [ADR-0003](../adr/0003-shared-state-file-layout.md).
- **OPEN-0.5.** Single-process-mode for development convenience? It would
  be tempting to allow `python server.py` to also start the HTTP server in
  a thread, for ease of testing during development. Trade-off: convenience
  vs. enforcing the two-process discipline. Decide in pass 2.
- **OPEN-0.6.** Web UI auto-launch from a Claude Code session — explicitly
  out of scope here, belongs to Epic 4. Recorded so it isn't accidentally
  scope-creeped into Epic 0.
