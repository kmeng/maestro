# Design: Epic 2 — project scaffolding

**Issue**: #14
**Status**: draft

> Pass-1 draft. Establishes the new-project vs take-over distinction and the
> additive / scoped / idempotent guarantees for take-over mode. The list of
> "collaboration essential" template files, the merge UX for pre-existing
> files, and version-skew handling are deferred to v0.0.3 design pass 2.

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
2. Maestro initializes a git repository.
3. Maestro lays down a full Maestro-flavored layout: collaboration
   essentials plus internal-project conventions. This includes everything
   a fresh Maestro-style project starts with — CLAUDE.md, docs/design/
   skeleton, docs/journal/ directory, ADR scheme, BUILD_LOG.md, the
   conventions Maestro itself uses.
4. Initial commit is made attributing both the user and Maestro.

### Take-over flow

1. User picks a directory containing an existing git repo.
2. Maestro analyzes the directory and presents a plan: "I will add files
   X, Y, Z. I will append a Maestro section to existing files A, B
   (showing the diff). I will not touch anything else."
3. User confirms or adjusts. Maestro applies changes.
4. Re-running the take-over flow shows "nothing to do" — the operation is
   idempotent.

The take-over flow is governed by three guarantees:

- **Additive.** Never overwrites existing user content. If a file already
  exists, Maestro either skips it or proposes a scoped append (e.g.,
  marked Maestro section in CLAUDE.md), never a rewrite.
- **Scoped.** Only files that are required for Maestro AI team
  collaboration are touched. Maestro's internal-project hygiene
  (BUILD_LOG.md, journal scheme, ADR scheme) stays out of take-over. The
  exact scope is pass-2 work.
- **Idempotent.** Re-running take-over produces no changes. This requires
  the appended sections in user files to be detectable (e.g., delimited)
  and the added files to be checked for content match before any write.

## Technical design

### Two template sets

The pass-2 work splits Maestro's governance corpus into two sets:

- **Collaboration essentials.** What a project needs in order to work
  with Maestro's AI team. Candidate inclusions (subject to pass-2 vetting):
  a Maestro section for CLAUDE.md describing the team and how to dispatch,
  a `.maestro/` config home (or project-local config files, depending on
  Epic 1 OPEN-1.1's resolution), a minimal docs/design/ entry-point if
  the project doesn't already have one.
- **Internal-project conventions.** What Maestro itself uses to govern
  itself. Candidate inclusions: BUILD_LOG.md, the journal directory and
  README, the full ADR scheme, full governance.md import, design doc
  template embedded in docs/design/. None of these go into take-over
  mode by default.

The pass-2 design produces an explicit list of files in each set with
rationale.

### Take-over mechanics

For each candidate template file, the take-over flow performs:

1. **Existence check.** If the destination doesn't exist, scheduled to
   add (subject to user confirmation).
2. **Content match check.** If it exists and matches the template, no-op
   (preserves idempotence).
3. **Mergeable file check.** For specific files (CLAUDE.md is the
   canonical case), if it exists and doesn't already contain Maestro's
   delimited section, scheduled to append the section. If it already
   contains the section, no-op or update-in-place when content differs.
4. **Conflict.** Any other case (non-mergeable file with conflicting
   content) is reported to the user as a manual decision, never
   auto-resolved.

The plan is shown to the user before any write. The user can deselect
individual items.

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

High-level milestones.

- [ ] T2.1 — Pass-2 design: split governance corpus into "collaboration essential" and "internal-project convention" template sets, with rationale per file
- [ ] T2.2 — Pass-2 design: merge UX for pre-existing files (CLAUDE.md is the canonical case)
- [ ] T2.3 — Pass-2 design: idempotence mechanism (delimited sections, content hashing, etc.)
- [ ] T2.4 — Implement: template set as packaged data
- [ ] T2.5 — Implement: new project flow (init git + lay down full layout)
- [ ] T2.6 — Implement: take-over flow plan generation
- [ ] T2.7 — Implement: take-over flow plan application
- [ ] T2.8 — Implement: Web UI for project selection + plan preview + apply
- [ ] T2.9 — Verify: take-over on a known existing project (Maestro itself? a sample real-world repo?) leaves the project working and adds only the agreed scope.

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

- **OPEN-2.1.** Exact membership of the "collaboration essential" template
  set vs the "internal-project convention" template set. Pass-2 design.
- **OPEN-2.2.** Merge UX for pre-existing CLAUDE.md (and any other
  mergeable file). Delimited section markers? Section header version?
  Pass-2 design.
- **OPEN-2.3.** Idempotence implementation. Content match by hash, by
  exact bytes, or by delimited-section-aware comparison? Pass-2 decision.
- **OPEN-2.4.** Version-skew between user's project and a Maestro upgrade.
  When Maestro v0.0.4 changes a template, what happens? Options: (a) leave
  user projects alone, document the migration; (b) detect drift and offer
  to update; (c) version each template section so updates can be opt-in.
  Trigger to decide: when v0.0.4 first changes a template, this becomes
  unavoidable. For v0.0.3, capture and defer.
- **OPEN-2.5.** "Uninstall Maestro" / "remove Maestro from this project"
  flow. Not in v0.0.3 scope. Trigger: a user explicitly asks for it, or
  take-over has misapplied somewhere and the user needs a clean revert.
- **OPEN-2.6.** Whether take-over should offer to register the project in
  any global Maestro state (e.g., a list of Maestro projects under
  `~/.maestro/projects.json`). Joint with Epic 0 OPEN-0.4 / Epic 1
  OPEN-1.1.
