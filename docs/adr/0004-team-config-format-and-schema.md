# ADR-0004: Team config — YAML format and role-keyed schema

**Status**: accepted
**Date**: 2026-05-08
**Issue**: #13

## Context

ADR-0003 placed team configuration at `<project-root>/.maestro/team.yaml`.
This ADR settles what's *in* that file: the format details, the schema,
and the conventions that will hold across v0.0.3 and beyond.

The decision is load-bearing for sibling epics:

- Epic 2 (project scaffolding) drops `team.yaml` into projects during
  the new-project flow, and merges or appends in take-over mode. It
  needs to know exactly what to write.
- Epic 3 (observability) reads role identifiers (`pm`, `senior`, …) from
  the dispatch log to label rows in the live view. It needs the role
  identifier set to be stable.
- The Web UI (Epic 0–1) reads, writes, and validates the file. The MCP
  server reads it to resolve "which model should `coder` use
  for this role" at dispatch time.

The file is end-user-visible: a contributor browsing the project will
see it; some users will hand-edit it. It is also primarily Web-UI-written.

## Decision

### Format: YAML

`team.yaml` is YAML. Read and written via `pyyaml`.

### Schema (version 1)

```yaml
# Maestro team configuration. Edit via the Web UI.
# Run `maestro-webui`, then open http://localhost:19830/team
# Schema reference: docs/design/13-epic1-team-composition.md
schema_version: 1

roles:
  pm:
    member: Alex
    model: claude-sonnet-4-6
  senior:
    member: Sam
    model: claude-sonnet-4-6
  junior:
    member: Jamie
    model: deepseek-coder
  documentarian:
    member: Drew
    model: qwen-plus
```

### Schema rules

- **`schema_version`** is required. v0.0.3 ships version `1`. Future
  schema changes increment this and ship a migrator.
- **`roles`** is a map keyed by role identifier. The four canonical
  identifiers are `pm`, `senior`, `junior`, `documentarian`. All four
  are required.
- Each role entry has exactly two fields, both required:
  - **`member`** — a string, the user-chosen alias.
  - **`model`** — a string, an explicit model identifier (no defaults
    in the file; the Web UI pre-fills the
    [`architecture.md`](../architecture.md) defaults but always writes
    the value explicitly).
- The map structure enforces 1 role : 1 member at the schema level.
  Two PMs cannot be expressed in this layout.
- The Architect role is **not** in the schema. It is the user's Claude
  Code main session and is not configurable here.

### In-code contract: Pydantic models

The schema is realized in code as Pydantic models in `maestro/team/` (or
equivalent — exact path resolved when implementation lands):

- `TeamConfig` — top-level model with `schema_version: int` and
  `roles: dict[RoleId, RoleEntry]`.
- `RoleEntry` — `member: str`, `model: str`.
- `RoleId` — Literal of the four identifiers.

The same Pydantic models serve:

- Web UI request/response schemas (Pydantic + FastAPI from ADR-0001).
- YAML round-trip (Pydantic dict ↔ `pyyaml`).
- MCP server's read-and-resolve at dispatch time.

One source of truth for the schema, in code.

### Comment policy

The Web UI writes a small header comment block (shown above) when it
creates the file. `pyyaml` does not preserve comments on round-trip; a
Web-UI-driven save will drop user-added comments inside the file. The
header is rewritten on each save. v0.0.3 accepts this trade-off in
exchange for `pyyaml`'s simplicity.

### Default model values

Defaults live in code, not in the file:

- A `DEFAULT_MODELS: dict[RoleId, str]` constant, sourced from
  `architecture.md`'s role-to-model bindings.
- The wizard pre-fills these when first creating `team.yaml`.
- The file always carries explicit `model:` values after first save —
  no implicit "use default" semantics.

If `architecture.md`'s defaults change in a future Maestro version,
existing user `team.yaml` files are unaffected (their values are
explicit). The wizard for new users gets the new defaults.

## Alternatives considered

- **JSON** — rejected. Stricter and more universal, but no comments,
  trailing-comma deaths on hand edits, and an aesthetically unfriendly
  surface for an end-user-visible file. The advantages JSON has over
  YAML (canonical encoding, parser uniformity) don't matter for a
  small local config file.
- **TOML** — rejected. Comment support and friendly hand-edit story
  are good, but Pydantic ↔ TOML round-trip has more friction than
  Pydantic ↔ YAML, and Maestro hasn't introduced TOML elsewhere.
  Adding a third format on top of YAML and JSON would clutter the
  project's surface for no concrete win.
- **List-of-roles structure** (e.g., `team: [{role: pm, member: Alex,
  ...}]`) — rejected for v0.0.3. Scales to 1:N more naturally but
  loses schema-level enforcement of the 1 role : 1 member constraint.
  Migration to this shape when 1:N becomes a real requirement is
  small and mechanical (the `roles:` map's `member: str` becomes
  `members: list[str]`, or the whole structure flattens). Trade
  current explicitness for future flexibility — pay the migration
  cost when (if) the trigger fires.
- **Lenient missing-field handling** (default in code if missing in
  file) — rejected. Two sources of truth (file + code defaults) drift.
  A file with explicit values is easier to reason about than one with
  implicit fallback semantics. Explicit-required is paired with the
  D4 fallback policy: when `team.yaml` is *absent entirely*, the MCP
  server falls back to v0.0.2 behavior — a clean, file-level fallback
  rather than a per-field one.
- **Defaults written into the file by the wizard** (current decision)
  vs **defaults left implicit and resolved at read time**. The chosen
  approach is "wizard pre-fills explicit defaults"; the rejected
  alternative would have left `model:` empty or absent and resolved
  to the code default at read time. Same drift problem as above.
- **Including Architect in the schema** — rejected. Architect is the
  user's Claude Code main session. There's no model to bind, no
  member to alias. Including it would invite confusion ("if I set
  this, does the orchestrator change?").
- **Comment-preserving YAML (`ruamel.yaml`)** — rejected for v0.0.3.
  Adds a heavier dependency for a small UX nicety (preserving user
  hand-edited comments through Web-UI saves). `pyyaml` is sufficient.
  Reconsider if user demand surfaces.

## Consequences

### Good

- **End-user-friendly.** YAML reads cleanly, allows comments, no
  trailing-comma traps. The Web UI writes a self-documenting header.
- **Schema enforces 1:1.** The map structure makes "two members for
  one role" impossible to express. Validation simpler at every layer.
- **One contract, one place.** Pydantic models do triple duty (Web UI
  I/O, YAML round-trip, MCP server read). No hand-written validators,
  no schema duplication.
- **`schema_version` from day one** turns future schema changes into
  bounded migrations rather than guessing games.
- **Architect excluded** keeps the file focused on the four
  instantiable roles and avoids the "is this configurable or not?"
  cognitive overhead.
- **Defaults in code, not in file** prevents implicit drift between
  what `team.yaml` says and what `architecture.md` says.

### Bad / risks

- **Comments drop on Web-UI saves.** A user who hand-edits comments
  inside the file (not the auto-rewritten header) loses them when
  the Web UI next saves. Mitigation: the Web UI's edit screen is the
  primary path; advanced users can be told. If demand surfaces, swap
  in `ruamel.yaml`.
- **1:N migration is a future cost.** When (if) we relax to 1:N,
  every existing user's `team.yaml` must be migrated. Mitigation:
  `schema_version` makes this a routine operation. Cost is real
  but bounded.
- **YAML's reputation for parsing surprises.** Mitigated by limited
  surface (small enum of known role IDs and model IDs) and validation
  (D2). The bug class doesn't apply at this scale.

### Reversibility

**Hard for the schema; easy for the format library.**

Format library swap (`pyyaml` → `ruamel.yaml`, e.g.) is a small
mechanical change — the on-disk format stays identical YAML.

Schema shape change (e.g., role-map → role-list) requires a
`schema_version` migrator that reads version 1 files and writes
version 2 files. Doable but real work; treat the v1 schema as
durable.

Format change (YAML → JSON or TOML) is the most expensive: every
existing user's file needs migration, the Pydantic round-trip layer
swaps out, the docs update. Treat the format as a lock-in.
