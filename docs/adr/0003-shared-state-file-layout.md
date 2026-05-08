# ADR-0003: Shared-state file layout — hybrid (project-primary, user-secondary)

**Status**: accepted
**Date**: 2026-05-08
**Issue**: #12

## Context

The v0.0.3 architecture has two processes (Web UI + MCP server) that share
state via the filesystem (see Epic 0, ADR-0001, ADR-0002). Several
sibling epics depend on knowing where that state lives:

- Epic 1 (team composition) writes role→model bindings and member aliases.
- Epic 2 (project scaffolding) lays down config files in user projects,
  with the additive / scoped / idempotent guarantees.
- Epic 3 (observability) writes a dispatch log from the MCP server and
  reads it from the Web UI.

This ADR pins down the **paths** at which these pieces of state live. It
deliberately leaves **schemas and formats** to the sibling epics: Epic 1
owns `team.yaml`'s contents, Epic 3 owns the dispatch log format.

A clean split is needed because some state is per-user (API credentials,
recent-projects list) and some is per-project (team composition, logs).
Picking one home for everything would force one of those to live in the
wrong place.

## Decision

Adopt a **hybrid layout**: each piece of state lives at the scope it
belongs to.

### User-global home: `~/.maestro/`

```
~/.maestro/
├── credentials.env       # API keys; never written by scaffolding into user projects
├── projects.json         # list of known project paths (UI's "recent projects")
└── settings.yaml         # user preferences (theme, default port, etc.)
```

- Owned by the user, shared across all projects.
- API keys live here — not in any project's `.env` by default. The
  v0.0.2 project-local `.env` loader path is preserved for backward
  compatibility (see "Migration").
- `projects.json` is a cache. If deleted or corrupted, the Web UI
  rebuilds it the next time the user picks a project.

### Project-local home: `<project-root>/.maestro/`

```
<project-root>/.maestro/
├── team.yaml             # role→model bindings, member aliases (Epic 1 schema)
├── logs/
│   └── dispatch.<format> # dispatch log (Epic 3 format)
└── .gitignore            # ships with: logs/
```

- Lives inside the user's git repo.
- `team.yaml` is **committed** by default. Team composition is a project
  decision — a contributor cloning the repo gets the same team setup.
- `logs/` is **gitignored**. Logs are bulky, churny, machine-written.
  The `.maestro/.gitignore` file is part of the scaffolding output (Epic
  2 writes it during project init / take-over).

### Path module

Both processes consume these paths through a single module —
`maestro/paths.py` (or equivalent) — that exposes:

- `user_home() -> Path`
- `credentials_env_path() -> Path`
- `projects_registry_path() -> Path`
- `user_settings_path() -> Path`
- `project_home(project_root: Path) -> Path`
- `team_config_path(project_root: Path) -> Path`
- `dispatch_log_path(project_root: Path) -> Path`

The signatures are pass-2 specification. Implementation is an Epic 0 PR.

### Migration: `.env` loader

v0.0.2 reads `DEEPSEEK_API_KEY` from a project-local `.env` (issue #6).
v0.0.3 extends the loader to also check `~/.maestro/credentials.env`.
Order of precedence (highest first):

1. Process environment (already exported)
2. Project-local `.env`
3. `~/.maestro/credentials.env`

The v0.0.2 path is preserved at higher precedence than the new one. No
behavior change for users who keep using project-local `.env`. New users
configuring through the Web UI get credentials written to
`~/.maestro/credentials.env` and never need to touch a project `.env`.

## Alternatives considered

- **Pure user-global (`~/.maestro/projects/<hash>/...`)** — rejected.
  Take-over mode (Epic 2) would have to register the project in
  user-global state and write to a hashed directory the user never sees.
  Different machines with the same repo cannot share team config without
  sync. Doesn't match the intuition that team composition is a project
  decision.
- **Pure project-local (`./.maestro/` only)** — rejected. API
  credentials cannot reasonably live in a directory committed to git;
  re-doing the v0.0.2 `.env` story under `.maestro/` reintroduces the
  same risk. User-global preferences and the recent-projects registry
  have no obvious home. Forces awkward placements.
- **All state in user-global, but with project paths used as keys** —
  rejected. Same problems as pure user-global plus an opaque keying
  scheme.
- **Skip user-global entirely; treat each project as fully
  self-contained** — rejected. Either credentials leak into git or every
  project re-prompts for them. Both are bad.

## Consequences

### Good

- Each state piece lives at the scope it belongs to. Mental model is
  clear: per-user vs per-project, no overlap.
- `team.yaml` is diffable, reviewable, version-controlled with the
  project — matches how `package.json` or `pyproject.toml` work.
- Take-over mode (Epic 2) is straightforward: writes `.maestro/team.yaml`
  and `.maestro/.gitignore` into the user's project. Both are additive
  and idempotent. No global registry write required for take-over to
  succeed.
- Logs are easy to find — `cd myproject && ls .maestro/logs/`.
- API credentials are off-limits to scaffolding writes by construction.
  Maestro never writes credentials into a user's project directory.
- Backward compatibility for `.env`: nobody's existing v0.0.2 setup
  breaks.

### Bad / risks

- **Two homes means two places to check.** Contributors have to learn
  the user/project split. Mitigation: `maestro/paths.py` is the single
  lookup point — code never hard-codes paths.
- **`.maestro/.gitignore` only matters if the user actually commits it.**
  If the user `git add .maestro/team.yaml` but skips `.maestro/.gitignore`,
  logs will eventually appear in their git status. Mitigation: scaffolding
  writes the `.gitignore` first and surfaces it in the plan preview
  (Epic 2 take-over flow).
- **`projects.json` is yet another place that could drift from
  reality** — projects get moved or deleted, and the registry doesn't
  notice. Mitigation: treat as a cache, validate on read, prune missing
  paths silently.
- **User-global `credentials.env` adds a new file the user has to know
  about.** Mitigation: Epic 1's first-launch wizard prompts for
  credentials and writes the file; user doesn't have to find it
  manually.

### Reversibility

**Medium.** Moving a piece of state from user-global to project-local
(or vice versa) is straightforward in the path module, plus a one-time
migration helper for existing installs. Restructuring the directory
layout entirely (e.g., flattening or merging homes) is more invasive
because tooling and docs anchor to it. Treat the user-global / project-
local split as durable; treat individual file names as adjustable.

## Sibling open questions resolved by this ADR

- Epic 0 OPEN-0.4 — config home (`~/.maestro/` vs project-local vs
  hybrid). Resolved: hybrid, as above.
- Epic 1 OPEN-1.1 — config storage location. Resolved: project-local
  `.maestro/team.yaml`. Schema (YAML format) lands as a separate Epic 1
  pass-2 decision (OPEN-1.2 stays open).
