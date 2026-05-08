# Design: v0.0.3 product vision — visualize Maestro for end users

**Issue**: #11
**Status**: draft

> This is a **pass-1 draft** that establishes the v0.0.3 skeleton across five
> epics. Each epic gets its own deeper pass-2 design round before code is
> written. Decisions here are coarse on purpose; ADR triggers are flagged
> rather than written.

## Problem

Through v0.0.2, Maestro is a developer-facing artifact: clone the repo, edit
config, manually wire the MCP server into Claude Code. This works for the
maintainer and a handful of early-adopter developers, but it is not a product
end users can pick up. The dogfooding-active future of Maestro depends on
non-developers being able to download Maestro, configure a team of AI
collaborators, scaffold or take over a project, and observe execution — all
through a guided surface, not by editing files.

v0.0.3 is the first release where Maestro itself becomes that surface. The
orchestrator role (Architect = the user's Claude Code main session) and the
MCP server runtime are unchanged. What's new is a localhost Web UI that
sits beside the runtime: configuring it before a session, observing it
during a session.

## Out of scope

- Code, in this round. This document and its five children are draft-only.
- Hosted / multi-user / cloud deployment. Maestro v0.0.3 is single-user
  local.
- Replacing the MCP server. The HTTP / Web UI surface is additive. The
  existing `cheap_code_gen` call path is non-negotiable and must not regress.
- Touching protected docs (README.md, CLAUDE.md, docs/governance.md,
  docs/architecture.md, existing ADRs). When v0.0.3's user surface lands, a
  README rewrite will be needed — that's a future, separate issue.

## Functional design

A user installs Maestro and double-clicks it (or runs a single command).
A localhost Web UI opens in their browser. They are guided through:

1. **Team composition** (Epic 1). A first-launch wizard introduces the four
   instantiable roles — Product Manager, Senior Engineer, Junior Engineer,
   Documentarian — names them as 1:1 members, and confirms the model bound
   to each role. The Architect role is intentionally absent: it is the
   user's Claude Code main session, not an instantiable member.
2. **Project scaffolding** (Epic 2). The user either creates a new project
   (Maestro inits a git repo and lays down a fresh Maestro-flavored layout)
   or takes over an existing project (Maestro additively, idempotently
   layers in only the files needed for AI team collaboration, never
   overwriting user content).
3. **Team observability** (Epic 3). Once Claude Code is dispatching work
   through Maestro's MCP tools, the Web UI shows a live execution flow,
   a dispatch log, and a problem panel for failures or human-in-the-loop
   questions.

The Web UI is a long-lived "Maestro app" the user launches independently of
any Claude Code session. The MCP server remains a stdio subprocess spawned
by Claude Code. The two processes share state via the filesystem.

Epic 4 (packaging into a single distributable) is deferred. v0.0.3 still
ships as a `git clone + run` artifact for early adopters, with the Web UI
launched manually.

## Technical design

### Process model

Two processes, shared filesystem state:

| Process | Lifecycle | Role |
|---|---|---|
| Web UI process | Long-lived, user-launched | Owns localhost HTTP. Reads/writes config. Tails dispatch log files. |
| MCP server process | Stdio subprocess of Claude Code (as today) | Reads config. Writes dispatch events to log files. |

The two never directly RPC each other. The shared-filesystem contract
(where config lives, where logs live, file formats) is defined by Epic 0
and consumed by Epics 1–3.

### Epic dependency graph

```
Epic 0 (skeleton + process model + shared-state contract)
   ├─ Epic 1 (team composition reads/writes config)
   │     └─ Epic 2 (project scaffolding uses team config)
   │           └─ Epic 3 (observability reads dispatch log written by MCP server)
   └─ Epic 4 (packaging — deferred, but constrained by 0)
```

Implementation order: 0 → 1 → 2 → 3.

### Affected modules

Per-epic detail is in the child design docs. At the vision level:

- New: a Web UI process (server + frontend), with a tech stack to be chosen
  in Epic 0 pass-2.
- New: a shared-state contract on the filesystem (config home, dispatch log
  location and format). Skeleton in Epic 0; consumed by 1, 2, 3.
- Existing MCP server: minimally extended in Epic 3 to emit dispatch events
  to the agreed log location. No public-interface changes for v0.0.3.

### Failure modes

Surfaced and resolved in child epics. At the vision level:

- HTTP server cannot bind to its preferred port — Epic 0 must define a
  fallback strategy.
- MCP and Web UI versions drift on the shared-state file format — Epic 0
  must define a versioning approach.
- Take-over mode encounters a project that already has a `CLAUDE.md` — Epic
  2 must define the merge / append UX.
- Dispatch log grows unbounded — Epic 3 must define a retention policy.

## Task breakdown

High-level milestones. Each milestone is a separate pass-2 design + multi-PR
implementation cycle, not a single task.

- [ ] M1 — Epic 0: process model, tech stack, empty-shell Web UI, shared-state contract skeleton (#12)
- [ ] M2 — Epic 1: team composition flow on top of the skeleton (#13)
- [ ] M3 — Epic 2: project scaffolding flow (new + take-over) (#14)
- [ ] M4 — Epic 3: dispatch-log instrumentation in MCP + execution-flow + problem-panel UI (#15)
- [ ] M5 — Epic 4: packaging — DEFERRED from v0.0.3 (#16)

## Acceptance criteria

For the v0.0.3 release as a whole (not for this draft):

- A first-time user can install Maestro, open the Web UI, and complete team
  composition without editing any file by hand.
- A first-time user can either create a new Maestro project or apply Maestro
  to one of their existing git repos via the Web UI.
- During a Claude Code session that uses Maestro's MCP server, the user can
  watch dispatches happen in the Web UI in something close to real time.
- The MCP `cheap_code_gen` path works exactly as it does in v0.0.2 — same
  call signature, same behavior. No regression.
- README.md, CLAUDE.md, governance.md, architecture.md, and existing ADRs
  are unchanged at the moment v0.0.3 ships (any required updates come in
  follow-up issues).

For this draft document specifically:

- All five child epic drafts exist and are linked from this doc and from
  their issues.
- All decisions explicitly deferred to pass 2 are listed in Open questions
  here or in the child docs.

## Open questions

Vision-level questions only. Epic-specific questions live in the child docs.

- **OPEN-V1.** Does v0.0.3 ship Epic 4? Currently deferred. Trigger to
  reconsider: if any of Epics 0–3 prove unusable without packaging (e.g.,
  the Web UI launcher is too painful to start manually), packaging gets
  promoted into v0.0.3 scope.
- **OPEN-V2.** 1 role : 1 member is the v0.0.3 model. Triggers to relax
  toward 1:N: (a) a user request to run two members of the same role in
  parallel; (b) a workload pattern where one role becomes a bottleneck and
  parallelism via multiple members is the cleanest fix. Until a trigger
  fires, dispatch is automatic and members are name-aliases only.
- **OPEN-V3.** README.md needs a substantial rewrite when v0.0.3 ships
  (Quick Start section becomes Web-UI-driven, install instructions change,
  feature list changes). H3 forbids touching it as a side effect of any
  v0.0.3 epic. Resolution: a dedicated "v0.0.3 README rewrite" issue,
  filed and merged after Epics 0–3 land.
- **OPEN-V4.** No labels are applied to the v0.0.3 epic issues today
  because the repo doesn't yet have a label scheme. Decide whether to
  introduce labels (e.g., `epic`, `v0.0.3`, `p0`) before pass-2 design
  starts on Epic 0.
