# Design: Epic 2 — project scaffolding

**Issue**: #14
**Status**: approved

> Approved after pass-2 (D1–D5, 2026-05-08). Template set membership,
> take-over merge mechanics, plan-preview UX, project registry
> semantics, and task breakdown are all resolved. Implementation tasks
> T2.1–T2.9 below are PR-sized closed loops, ready to land in order
> against `v0.0.3` after Epic 0 T0.1/T0.3/T0.4 land first (T2.8 also
> depends on Epic 1 T1.4).
>
> ADRs produced: [0005](../adr/0005-scaffolding-template-set.md),
> [0006](../adr/0006-take-over-merge-mechanics.md).

## Problem

Today, applying Maestro to a project means manual git work and manual
copying of governance files (CLAUDE.md, design doc layout, journal
directory). Two scenarios fail this approach:

- **New project.** A user wants to start a project with Maestro from day
  one. They shouldn't have to know Maestro's internal file layout to do
  this.
- **Existing project.** A user has a real codebase and wants to apply
  Maestro on top of it. They cannot afford for Maestro to overwrite their
  README, their docs structure, their existing AI-collaboration
  instructions, or anything else they've built. They want only the
  Maestro-specific bits added — and only where there's no conflict.

Epic 2 makes both scenarios visual flows in the Web UI, with the take-over
flow built around three guarantees: additive, scoped, idempotent.

## Out of scope

- Multi-project switching UI. v0.0.3 assumes one project at a time. The
  Web UI is "in" a project once the user picks one.
- Auto-discovery of existing projects on disk. The user points Maestro at
  a directory; Maestro doesn't crawl the filesystem.
- Imposing Maestro's internal-project conventions on user projects in
  take-over mode. BUILD_LOG.md, the journal scheme, ADR conventions, and
  the like are Maestro's own internal-project hygiene. They go into
  new-project mode only. Take-over mode is strictly the minimum needed
  for Maestro AI team collaboration to work.
- Template versioning across Maestro releases. When Maestro v0.0.4 changes
  a template, what happens to projects scaffolded under v0.0.3? Open
  question, deferred.
- Removing Maestro from a project ("uninstall"). Tracked but not in
  v0.0.3.

## Functional design

The user picks a project directory in the Web UI. Maestro detects whether
the directory is empty (or non-existent) versus already-a-project, and
offers the appropriate flow.

### New project flow

1. User picks a directory (empty / non-existent).
2. Maestro runs pre-flight (D2): verifies the directory is empty.
3. Maestro initializes a git repository.
4. Maestro lays down the new-project file set from D1 (`.gitignore`,
   `README.md`, `CLAUDE.md`, `.maestro/.gitignore`).
5. Initial commit is made.
6. The wizard (Epic 1) launches automatically and writes
   `.maestro/team.yaml`.

The plan-preview UX (described under "Take-over flow" below) also
applies here — the user sees what will be written before any write
happens.

### Take-over flow

1. User picks a directory containing an existing git repo.
2. Maestro runs pre-flight (D2): verifies `.git/` exists, working tree
   is clean, no unexpected `.maestro/` content. Pre-flight failures
   surface in the plan-preview banner; apply is disabled until they
   are resolved.
3. Maestro generates a plan — for each file in the take-over set
   (`.maestro/.gitignore`, `CLAUDE.md`), a `(file, op, detail)` row.
4. The plan-preview UX shows the user what will happen, with full
   drill-down on every row.
5. User confirms apply. Maestro writes file by file with streaming
   per-file results.
6. The wizard (Epic 1) launches automatically and writes
   `.maestro/team.yaml`.
7. Re-running take-over on the same project shows everything as
   `NOOP` — idempotence holds.

#### Plan-preview UX (decided in pass-2 D3)

A three-layer disclosure surface:

- **Pre-flight banner** at the top — current project path, plus a
  summary of the pre-flight checks (✓ git repo, ✓ clean tree, ✓ no
  existing `.maestro/`). Failed checks render prominently and disable
  the Apply button.
- **Plan overview** — one row per planned file, grouped by op type.
  Each row shows op badge (color-coded), file path, one-line summary,
  a disclosure toggle for details, and an opt-out checkbox for
  `CREATE` / `APPEND_DELIMITED` ops only.
- **Per-row drill-down** — clicking a row expands to show the actual
  content that will be written, the existing content (if any), and a
  unified diff for `APPEND_DELIMITED`. For `CONFLICT` rows, the
  specific reason and two action buttons (Skip / Open file).

#### Conflict handling

There is **no "force overwrite" button.** The user resolves conflicts
by editing the file themselves (Open file → fix → close) and
re-running the plan. The plan re-evaluates idempotence on the next
generation; what was `CONFLICT` may now be `NOOP`. Intentional
friction — makes "Maestro overwrote my CLAUDE.md" impossible by
construction.

Required-file conflicts (CLAUDE.md, `.maestro/.gitignore` in
take-over) block apply. Optional-file conflicts (none in v0.0.3) do
not.

#### Apply behavior

- Apply button **disabled** if any pre-flight check fails, or any
  required-file `CONFLICT` is unresolved, or all opt-out checkboxes
  are unchecked.
- Apply button **enabled with a confirm modal** otherwise.
- On confirm, the engine applies file by file. Per-file results
  stream via SSE (`sse-starlette` from [ADR-0001](../adr/0001-web-framework-fastapi.md)):

  ```
  event: file_started   data: { path: "CLAUDE.md" }
  event: file_succeeded data: { path: "CLAUDE.md" }
  event: file_failed    data: { path: ".maestro/.gitignore", error: "..." }
  event: plan_complete  data: { succeeded: N, failed: M }
  ```

  The Web UI updates each row's state in real time.

#### Three guarantees, made concrete

- **Additive** is enforced by the operation taxonomy in
  [ADR-0006](../adr/0006-take-over-merge-mechanics.md): no `OVERWRITE`
  op exists; user content is never replaced silently.
- **Scoped** is enforced by D1's deliberately small file lists.
- **Idempotent** is enforced by per-file rules in ADR-0006: byte
  match for replacement files, delimiter scan for mergeable files.

### Language

Web UI surfaces in this epic are **Chinese**: page headings, op
badges, summary lines ("将创建 .maestro/.gitignore"), button labels,
modal text, error messages. File paths and the *content* of files
shown in drill-down stay verbatim — Maestro doesn't translate user
content or template content. CLAUDE.md Maestro section content is
English regardless (Claude Code is the reader; see ADR-0005).

Per the cross-cutting [Epic 1 Language section](13-epic1-team-composition.md#language).

## Technical design

### Template sets — decided

Pass-2 D1 resolves both sets. Full rationale in
[ADR-0005](../adr/0005-scaffolding-template-set.md).

#### Take-over set (2 files)

| File | Content | Language |
|---|---|---|
| `.maestro/.gitignore` | `logs/` | (no prose) |
| `CLAUDE.md` | Delimited Maestro section appended (or full file if absent) | English (Claude Code reads it) |

The wizard runs after take-over and writes `.maestro/team.yaml` —
take-over itself does not.

#### New-project set (4 files)

| File | Content | Language |
|---|---|---|
| `.gitignore` | Python defaults + `.maestro/logs/` | (no prose) |
| `README.md` | One-paragraph project stub | Chinese |
| `CLAUDE.md` | Delimited Maestro section + user placeholder | English / Chinese (mixed by reader) |
| `.maestro/.gitignore` | `logs/` | (no prose) |

`git init` runs first; the wizard runs after to write `team.yaml`.

#### Internal-project convention set — deliberately not shipped

`BUILD_LOG.md`, `docs/journal/`, `docs/design/` template, `docs/adr/`
template, `docs/governance.md`, `docs/architecture.md`,
`docs/known-issues.md`, `ROADMAP.md` — none of these go into either
set. They are Maestro's internal hygiene; user projects that want
them can copy from Maestro's repo. Rationale in ADR-0005.

#### CLAUDE.md Maestro section format

Delimited by `<!-- maestro:start v=1 -->` / `<!-- maestro:end v=1 -->`.
HTML comments — invisible in rendered markdown, unambiguous in
substring search. Versioned on the delimiter so future content
changes ship with a migration path. H2 heading (`##`) so it slots in
regardless of the host file's heading style. English content — Claude
Code is the reader.

### Scaffolding engine — operation model

Both flows (new-project and take-over) run through one engine
parameterized by the file list (D1) and the merge mechanics decided
in pass-2 D2. Full rationale in
[ADR-0006](../adr/0006-take-over-merge-mechanics.md).

#### Operation taxonomy

Each candidate file resolves to exactly one operation:

| Op | Trigger |
|---|---|
| `CREATE` | Destination doesn't exist → atomic write of rendered template |
| `APPEND_DELIMITED` | Destination exists, no Maestro section, and file is mergeable (CLAUDE.md only) → atomic append of delimited section |
| `NOOP` | Destination already matches the would-be result |
| `CONFLICT` | Anything else — surfaced to the user, never auto-resolved |

Plan generation walks the file list once and produces an ordered list
of `(file, op, detail)` tuples for the plan preview UX (D3).

#### Idempotence

- **Pure-replacement files** (`.maestro/.gitignore`, `.gitignore`,
  `README.md`): exact-bytes match between disk and rendered template.
- **Mergeable files** (CLAUDE.md): delimiter scan for
  `<!-- maestro:start v=1 -->` … `<!-- maestro:end v=1 -->` blocks.
  Whitespace stripped at the section boundaries before comparison;
  any other byte difference inside the block is `CONFLICT`. Older or
  unknown `v=N` versions also `CONFLICT` (no auto-migration in
  v0.0.3).

#### Atomicity

Per-file atomic via `os.replace` (write-then-rename). Not
transactional across multiple files — partial-apply is bounded by
the small file lists (4 max for new-project, 2 for take-over) and
recoverable by an idempotent re-run.

#### Pre-flight checks

Run before any plan can be applied:

1. Project root resolves and is a directory.
2. Git state matches the flow: take-over requires `.git/`;
   new-project requires empty / non-existent directory.
3. (Take-over only) `git status --porcelain` is empty — refuse on a
   dirty tree with a clear "commit, stash, or explicitly confirm"
   message.
4. (Take-over only) No unexpected `.maestro/` content beyond what
   take-over would produce — surface as `CONFLICT` rows.

#### What the engine does not do

- **No in-place rewriting.** Every write is full-file replacement of
  rendered content (mergeable files splice the new section in in
  memory before atomic write).
- **No backup files.** Pre-flight uncommitted-changes check makes git
  itself the rollback mechanism.
- **No auto-resolution of conflicts.** Every `CONFLICT` is the user's
  decision via the plan preview.
- **Line endings:** writes always LF. Reads tolerate CRLF by
  normalizing to LF for comparison.

### Project registry — `~/.maestro/projects.json`

The user-global recent-projects cache established in
[ADR-0003](../adr/0003-shared-state-file-layout.md). v0.0.3 settles
the schema and write semantics inline (cache concerns are reversible;
no ADR).

#### Schema

```json
{
  "schema_version": 1,
  "projects": [
    {
      "path": "/Users/alice/projects/myapp",
      "last_opened_at": "2026-05-08T14:23:11Z"
    }
  ]
}
```

`schema_version: 1` from day one for migration safety. No display
name (the UI uses `basename(path)`), no team-summary cache (re-reads
`team.yaml` cheaply on each open), no statistics.

#### When to write

| Event | Registry write? |
|---|---|
| Web UI opens (read existing) | No write |
| User picks directory; plan preview renders | No write |
| Apply succeeds | **Write**: upsert entry with `last_opened_at = now` |
| Apply partially succeeds (some files written, some failed) | **Write**: upsert entry. The project has Maestro writes — counts as known. |
| Pre-flight aborts before any write | No write |
| User cancels mid-preview | No write |
| User opens a known project from recent-projects | **Write**: bump `last_opened_at` |
| User re-runs apply on a known project | **Write on success**: bump `last_opened_at` |

The first concrete user commitment is clicking Apply. Browsing through
the plan-preview without applying does not pollute the recent-projects
list.

#### Pruning and corruption tolerance

- **Read-time pruning**: silently drop entries whose `path` no longer
  exists on disk. Lazy write-back on the next event that writes
  anyway — no thrashing.
- **Unrecognized `schema_version`**: treat as absent, rebuild on next
  write. No migration UX in v0.0.3.
- **Parse failure (corrupt JSON)**: treat as absent, rebuild. Don't
  surface to the user — this is a cache.

### Affected modules

- New: `maestro/scaffold/` (or similar) — the template set, the new vs
  take-over flow logic, the merge engine for delimited sections.
- New: Web UI screens for project selection, plan preview, confirmation.
- New: HTTP API endpoints for plan generation and plan application.
- Existing: nothing in the MCP server changes for Epic 2. The MCP server
  reads team config (Epic 1's contract); scaffolding doesn't change that
  contract.

### Failure modes

- **User points at a non-git directory.** Offer to `git init`. Don't
  silently do it.
- **User points at a git directory with uncommitted changes.** Show the
  uncommitted changes; refuse to write until the user has committed,
  stashed, or explicitly confirmed.
- **A template file write fails partway.** Atomic-per-file. Show what
  succeeded and what didn't. No transactional rollback in v0.0.3 — but
  no orphaned partial state either.
- **CLAUDE.md exists with a Maestro section that's stale (older Maestro
  version).** Pass-2 question: how does take-over know "stale" vs "user
  has hand-edited"? Versioning the section header is one option.

## Task breakdown

PR-sized closed loops. Each PR keeps `main` runnable. **Prerequisite**:
Epic 0 T0.1 (paths module), T0.3 (FastAPI app), T0.4 (empty-shell page)
must land before T2.1 starts. T2.8 also depends on Epic 1 T1.4 (wizard
UI).

- [ ] **T2.1** — Scaffolding engine in `maestro/scaffold/`: operation types (`CREATE` / `APPEND_DELIMITED` / `NOOP` / `CONFLICT`) per [ADR-0006](../adr/0006-take-over-merge-mechanics.md), plan-generation logic. Pure data + logic, no I/O. Unit tests against synthetic file states. (~2h)
- [ ] **T2.2** — File I/O layer: atomic write-then-rename, CRLF-tolerant reads, apply executor that walks a plan and emits per-file events. No-op call from T0.3's webui module so the module is exercised. Integration tests applying plans to temp directories. (~1.5h)
- [ ] **T2.3** — Pre-flight checks (directory existence, git state, clean tree, unexpected `.maestro/`). Wired into plan generation — failures appear as plan rows. (~1h)
- [ ] **T2.4** — Template content as packaged data per [ADR-0005](../adr/0005-scaffolding-template-set.md): CLAUDE.md Maestro section template body, README stub, `.gitignore`, `.maestro/.gitignore`. Renderer substitutes Maestro version into delimiters. Byte-stable output for fixed inputs. (~1h)
- [ ] **T2.5** — Project registry module — read/write `~/.maestro/projects.json` per D4 schema and write semantics. Independent of the scaffolding engine. Unit tests on read/write/prune/upsert + corruption tolerance. (~1h)
- [ ] **T2.6** — HTTP API endpoints: `POST /api/scaffold/plan` returns plan JSON (file rows + pre-flight banner); `POST /api/scaffold/apply` is an SSE endpoint streaming per-file events + `plan_complete`. On `plan_complete`, registers the project (T2.5). (~1.5h)
- [ ] **T2.7** — Web UI screens: project picker, plan preview (3-layer disclosure), per-row drill-down with diff rendering for `APPEND_DELIMITED`, conflict-resolution UX (Skip / Open file). Copy in Chinese per D6. (~2h)
- [ ] **T2.8** — Wire auto-launch of Epic 1's wizard after successful apply. Depends on Epic 1 T1.4. (~30m)
- [ ] **T2.9** — End-to-end verification PR. Documented manual smoke: new-project flow → wizard → `cheap_code_gen`; take-over → wizard → `cheap_code_gen`; partial-apply failure recovery; idempotent re-run; v0.0.2 regression check (project with no `.maestro/` still works). (~1.5h)

T2.4 and T2.5 are parallelizable with T2.1–T2.3.

## Acceptance criteria

- A user can create a new Maestro project via the Web UI: empty directory
  in, working Maestro-flavored project (with git history) out.
- A user can apply Maestro to an existing git repo via the Web UI without
  any pre-existing user file being overwritten.
- A user re-running take-over on the same project sees "nothing to do."
  Idempotence holds.
- Take-over does not add Maestro internal-project conventions
  (BUILD_LOG.md, journal scheme, ADR scheme) to the user's project.
- A pre-existing CLAUDE.md is appended to with a clearly-delimited
  Maestro section, never replaced.
- A pre-existing file conflict that can't be auto-resolved surfaces as a
  user-facing decision, not a silent skip and not an overwrite.

## Open questions

- ~~**OPEN-2.1.** Exact membership of the "collaboration essential" template set vs the "internal-project convention" template set.~~ **Resolved**: take-over set is `.maestro/.gitignore` + delimited CLAUDE.md section; new-project set adds `.gitignore` + `README.md` stub. Internal-project conventions are explicitly excluded. See [ADR-0005](../adr/0005-scaffolding-template-set.md).
- ~~**OPEN-2.2.** Merge UX for pre-existing CLAUDE.md.~~ **Resolved**: HTML-comment delimiters `<!-- maestro:start v=1 -->` / `<!-- maestro:end v=1 -->`, versioned for future migration. See [ADR-0005](../adr/0005-scaffolding-template-set.md) (format) and [ADR-0006](../adr/0006-take-over-merge-mechanics.md) (mechanics).
- ~~**OPEN-2.3.** Idempotence implementation.~~ **Resolved**: byte-match for replacement files; delimiter scan with leading/trailing whitespace tolerance for mergeable files; older or unknown `v=N` versions are `CONFLICT`. See [ADR-0006](../adr/0006-take-over-merge-mechanics.md).
- **OPEN-2.4.** Version-skew between user's project and a Maestro upgrade.
  When Maestro v0.0.4 changes a template, what happens? Options: (a) leave
  user projects alone, document the migration; (b) detect drift and offer
  to update; (c) version each template section so updates can be opt-in.
  Trigger to decide: when v0.0.4 first changes a template, this becomes
  unavoidable. For v0.0.3, capture and defer.
- **OPEN-2.5.** "Uninstall Maestro" / "remove Maestro from this project"
  flow. Not in v0.0.3 scope. Trigger: a user explicitly asks for it, or
  take-over has misapplied somewhere and the user needs a clean revert.
- ~~**OPEN-2.6.** Whether take-over should register the project in `~/.maestro/projects.json`.~~ **Resolved**: yes, on apply success (or partial-apply); never on plan-preview browse or pre-flight abort. Schema and write events specified in the "Project registry" subsection above.
