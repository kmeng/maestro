# ADR-0005: Project scaffolding — template set membership

**Status**: accepted
**Date**: 2026-05-08
**Issue**: #14

## Context

Epic 2 (project scaffolding) has two flows:

- **New-project flow.** Maestro creates a fresh project from nothing
  (`git init` plus a small Maestro-flavored layout).
- **Take-over flow.** Maestro adds the minimum needed for AI team
  coordination to an existing project, with the additive / scoped /
  idempotent guarantees from the original Epic 2 design draft.

Both flows write files into the user's filesystem. Each file is a
contract: changing it later is harder than getting it right now. This
ADR settles the membership of those file sets.

The decision is constrained by two principles already established:

- **"Take-over is scoped."** Maestro doesn't impose its internal-project
  conventions (BUILD_LOG.md, journal scheme, ADR scheme, etc.) on user
  projects. Those are Maestro's own hygiene; user projects have their
  own.
- **"Language depends on reader."** Per [Epic 1 — Language](../design/13-epic1-team-composition.md#language).
  Files Claude Code reads as instructions are English; files the user
  reads as prose are Chinese.

## Decision

### Take-over set (2 files; additive to existing project)

| File | Content | Language |
|---|---|---|
| `.maestro/.gitignore` | Single line: `logs/` | (no prose) |
| `CLAUDE.md` | Delimited Maestro section, appended if the file exists, or full Maestro-flavored CLAUDE.md if it doesn't | English (Claude Code reads it) |

The wizard runs immediately after take-over and writes
`.maestro/team.yaml`. Take-over itself does **not** write `team.yaml` —
that's the wizard's job. This keeps take-over's writes idempotent and
keeps team-configuration as a deliberate user act.

### New-project set (4 files; fresh init)

| File | Content | Language |
|---|---|---|
| `.gitignore` | Python-friendly defaults (`__pycache__`, `.env`, `*.egg-info`, etc.) plus `.maestro/logs/` | (no prose) |
| `README.md` | One-paragraph project stub | Chinese (user reads it) |
| `CLAUDE.md` | Delimited Maestro section + "your project rules go here" placeholder | English for the Maestro section; Chinese for the user-facing placeholder |
| `.maestro/.gitignore` | Single line: `logs/` | (no prose) |

Plus: `git init` runs first, the wizard runs after and writes
`.maestro/team.yaml`.

### Internal-project convention set — deliberately not shipped

The following files are part of *Maestro's own internal-project
hygiene* and are **not** included in either set:

- `BUILD_LOG.md` — Maestro's per-release AI authorship + cost log
- `docs/journal/` and `docs/journal/README.md` — Maestro's
  cross-session shared-memory mechanism
- `docs/design/` directory layout and design-doc template
- `docs/adr/` directory and ADR template
- `docs/governance.md` — Maestro's process governance
- `docs/architecture.md` — Maestro's architectural principles
- `docs/known-issues.md` — Maestro's exception log
- `ROADMAP.md` — Maestro's roadmap

A user who wants any of these is welcome to copy from Maestro's own
repo. Maestro the *tool* is responsible for AI team coordination —
not for prescribing how the user's project is governed.

### CLAUDE.md Maestro section — shape

The actual content is implementation-time work. The shape — what
must be true regardless of the wording — is:

- **Delimited** by `<!-- maestro:start v=1 -->` and
  `<!-- maestro:end v=1 -->`. HTML comments — invisible in rendered
  markdown, unambiguous to find with substring search.
- **Versioned** on the delimiters (`v=1`). When future Maestro
  releases materially change the section content, the version
  increments and a migration path is defined (see
  [OPEN-2.4](../design/14-epic2-project-scaffolding.md#open-questions)).
- **H2 heading** (`##`) so it slots into existing CLAUDE.md files
  whether the host uses H1 for the title or not.
- **English** content — Claude Code is the reader.
- **Substantively informative**: tells Claude Code that this project
  uses Maestro, where the team config lives, that Architect is the
  Claude Code session itself, that dispatch goes through MCP tools,
  and that team-config changes happen in the Web UI.

A working sketch (not the final wording):

```markdown
<!-- maestro:start v=1 -->
## AI team coordination via Maestro

This project uses Maestro to coordinate multiple AI workers. Team
configuration lives in `.maestro/team.yaml`. Roles available: Product
Manager, Senior Engineer, Junior Engineer, Documentarian.

When you (Claude Code, in the Architect role) need to delegate
implementation, code generation, or documentation work, dispatch to a
role via the Maestro MCP tools. The role's bound model handles the
work; results flow back to you. Architect — that's you — orchestrates.

Configuration changes happen in the Maestro Web UI (run `maestro-webui`).
Do not hand-edit `.maestro/team.yaml` unless you know what you're doing.
<!-- maestro:end v=1 -->
```

## Alternatives considered

- **Wider take-over set** — drop `BUILD_LOG.md`, journal scheme, design
  template, and similar into user projects too. Rejected. Most of
  Maestro's governance corpus is *about Maestro*, not about projects
  *using* Maestro. Imposing it would be the same overreach as Django
  shipping its own contributors' guide into every Django project.
- **Narrower take-over set** — skip CLAUDE.md entirely, leave the
  user to add a Maestro section by hand if they want. Rejected.
  Without a CLAUDE.md Maestro section, Claude Code has no way to know
  the project uses Maestro, and dispatch would require explicit user
  prompting every time. Take-over's whole point is "make Maestro work
  in this project"; skipping CLAUDE.md defeats that.
- **Always replace CLAUDE.md** rather than append-with-delimiters.
  Rejected — violates the additive guarantee. User-authored content
  is sacred.
- **No version on delimiters** — just `<!-- maestro:start -->` /
  `<!-- maestro:end -->`. Rejected. Without a version, the first time
  Maestro changes the section content we have no way to detect
  "this is the old shape, migrate" vs "user has hand-edited, leave
  alone." Versioning costs nothing today, saves design work in the
  first migration.
- **Localize the CLAUDE.md Maestro section** — translate it to
  Chinese to match the user-facing language. Rejected. Claude Code is
  the reader; English is its native instruction-following surface;
  Chinese instructions would work but worse for no benefit. The "user
  is Chinese-speaking" constraint applies to surfaces the user reads,
  not to surfaces machines read.
- **Translate `README.md` and the CLAUDE.md placeholder to English** —
  match Maestro's own repo. Rejected. The user is the reader; the
  user is Chinese-speaking; consistency-with-Maestro's-own-repo is not
  a goal.

## Consequences

### Good

- **Sharply minimal take-over surface.** Two files. Easier to reason
  about, easier to undo, easier for the user to trust.
- **CLAUDE.md is the load-bearing piece.** Once the Maestro section
  is delimited and versioned, every future Maestro release has a
  clean migration path.
- **No cargo-culting Maestro's hygiene.** A user project that uses
  Maestro doesn't end up with `BUILD_LOG.md` it never wanted, or a
  journal directory it'll never fill in.
- **Reader-driven language** keeps each file appropriate for its
  consumer. Claude Code gets English; the user gets Chinese; no file
  gets both unless it has to (the `CLAUDE.md` placeholder, which is
  user-facing prose embedded in an otherwise-Claude-Code file).
- **New-project set is small enough to inspect.** A user reviewing
  what Maestro just dropped into their fresh project sees four files,
  not a tree of opinionated boilerplate.

### Bad / risks

- **The take-over CLAUDE.md append is the most user-sensitive write
  Maestro does.** Mistakes here (wrong delimiters, accidental
  overwrite, broken markdown) are visible immediately. Mitigation:
  D2's merge mechanics specify atomic write-then-rename, plan-preview
  shows the diff before applying, and the delimiters are precisely
  scoped strings.
- **A user might want richer scaffolding** (e.g., the journal scheme
  is genuinely useful for some teams). They'll have to copy from
  Maestro's repo manually. Mitigation: this is recoverable; we can
  add an "advanced scaffold" toggle in a future release if user
  demand surfaces. For v0.0.3, minimalism wins.
- **Two scaffolding code paths** (new vs take-over) means two ways
  to be wrong. Mitigation: implement them as one engine with a
  parameterized "what to write" — the engine is the same; the file
  list differs. D2 will pin this down.
- **English Maestro section in a Chinese-language project** could
  feel inconsistent to a contributor reading the project. Mitigation:
  the section is delimited and explicitly machine-targeted; the
  delimiter comments make this legible. We can revisit if reports
  surface.

### Reversibility

- **Take-over set membership: medium.** Adding a third file later
  (say, a Maestro section in `.gitignore` for project-root concerns)
  means existing take-over installs don't have it; a re-run of
  take-over would add it idempotently, but old installs need a manual
  trigger.
- **New-project set membership: low cost to change.** Each new project
  is independent; changes only affect future projects.
- **Delimiter format: hard.** Once user projects in the wild have
  `<!-- maestro:start v=1 -->`, changing to a different delimiter
  syntax requires migration code that finds the old form and
  rewrites. Treat this format as durable.
- **CLAUDE.md section content: medium.** Versioned on the delimiter
  precisely so this can change in v2 without breaking v1
  installations — the migration finds `v=1` blocks and rewrites them
  to `v=2`. Pre-planned reversibility.
