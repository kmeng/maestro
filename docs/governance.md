# Maestro Project Governance

This document defines how Maestro is built. It binds all contributors — human and AI — to a shared workflow.

For architectural principles, see [`architecture.md`](architecture.md).
For Claude Code's operating rules, see [`../CLAUDE.md`](../CLAUDE.md).

When in doubt, follow this document. When this document is wrong, update it before the code.

---

## Lifecycle of any change

```
1. INTAKE       Issue created, tagged: feature / bug / refactor / docs
       ↓
2. ANALYSIS     Understand the need, scope, acceptance criteria
                → updates issue body
       ↓
3. DESIGN       Functional design + technical design + ADR if needed
                → docs/design/<n>-<slug>.md, docs/adr/NNNN-title.md
       ↓
4. APPROVAL     Maintainer approves design before any code is written
       ↓
5. BREAKDOWN    Split into small closed loops, ~30min–2h each
                → tracked as checkboxes in the issue
       ↓
6. IMPLEMENT    One task = one branch = one PR
                Each PR keeps the system runnable
       ↓
7. INTEGRATE    PR reviewed, merged
                BUILD_LOG.md updated for AI contributions
       ↓
8. CLOSE        Issue closed when all tasks done AND acceptance met
```

---

## The Closed Loop Rule (核心)

Every task, no matter how small, must produce **a runnable system**. The repo on `main` is always green: clone → install → run → works.

This means:
- A task that adds a function but no caller is not allowed — either also add the caller, or stub the caller, or skip the task
- A task that breaks an existing test is not allowed to merge until the test is fixed in the same PR
- A task that requires "follow-up work to be useful" is too big — split it differently

### Right vs wrong split

**Wrong** (breaks the loop):
- PR 1: add new config schema (breaks existing config loading)

**Right** (each PR keeps system runnable):
- PR 1: add new config schema with backward compatibility, no callers using new fields yet
- PR 2: migrate one caller to new schema
- PR 3: migrate remaining callers
- PR 4: remove deprecated old schema

---

## Branch and commit conventions

### Branches

| Prefix | Use for |
|---|---|
| `feature/<n>-<slug>` | new functionality |
| `fix/<n>-<slug>` | bug fix |
| `refactor/<n>-<slug>` | internal restructure, no behavior change |
| `docs/<n>-<slug>` | documentation only |
| `bootstrap/<version>` | special, only for v0.0.x foundational work |

`<n>` is the GitHub issue number. `<slug>` is a short kebab-case name.

### Commit messages (Conventional Commits)

```
<type>: <short summary, imperative mood>

<optional body explaining why, not what>

<optional footer: Closes #N, Refs #M, Co-authored-by>
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`.

### AI authorship attribution (mandatory)

When AI generates substantive code, the commit must include:

```
Co-authored-by: claude-opus <noreply@anthropic.com>
Co-authored-by: deepseek-coder <noreply@deepseek.com>
```

Use the model name actually responsible. Multiple co-authors are allowed.

---

## Pull Request rules

- One PR = one task = one closed loop
- PR description must include: linked issue, what changed, how to verify
- Squash-merge to main; no merge commits in main
- PR > 400 lines: justify in the description or split

In solo phase, the maintainer reviews their own PRs after a 24-hour cooling-off period, OR explicitly self-approves with rationale in the PR description.

---

## Architecture Decision Records (ADRs)

Whenever a design choice has long-term consequences, write a one-pager ADR.

### Triggers

- Choosing a new external dependency
- Changing the public interface of an MCP tool
- Introducing a new role or worker type
- Changing how state is stored, logged, or transmitted
- Anything where future-you will ask "why did we do this?"

### ADR template

Lives in `docs/adr/NNNN-title.md`:

```markdown
# ADR-NNNN: <decision title>

**Status**: proposed | accepted | superseded by ADR-XXXX
**Date**: YYYY-MM-DD
**Issue**: #N

## Context
What's the situation? What problem are we solving?

## Decision
What did we decide?

## Alternatives considered
- Option A: ... — rejected because ...
- Option B: ... — rejected because ...

## Consequences
- Good: ...
- Bad / risks: ...
- Reversibility: easy / hard / irreversible
```

---

## Functional design documents

Every feature needs a design doc at `docs/design/<n>-<slug>.md` before code is written.

### Template

```markdown
# Design: <feature name>

**Issue**: #N
**Status**: draft | approved | implemented

## Problem
What user need are we solving?

## Out of scope
What we explicitly are not doing.

## Functional design
What the user / caller experiences.

## Technical design
- Affected modules
- New interfaces (signatures, schemas)
- Data shapes
- Failure modes and how they're surfaced

## Task breakdown
- [ ] Task 1: ...
- [ ] Task 2: ...
- [ ] Task 3: ...

## Acceptance criteria
- ...

## Open questions
- ...
```

---

## Bug fix workflow

Bugs follow the same lifecycle, with one addition: **a failing test must exist before the fix**.

```
1. Reproduce the bug → write a test that fails because of it
2. Commit the failing test (in the bugfix branch)
3. Fix the bug → test passes
4. Commit the fix
5. PR contains both commits, in that order
```

This is non-negotiable. A bug without a regression test is a bug that will come back.

**Exception**: bugs that cannot be tested in CI (e.g. flaky external API behavior). Document in `docs/known-issues.md` and add defensive code with a comment linking to the doc.

---

## Documentation rules

A change is not done until the docs reflect it.

| Doc | Purpose | Updated when |
|---|---|---|
| `README.md` | Project pitch, quick start | Public interface changes |
| `CLAUDE.md` | AI contributor operating rules | Workflow changes |
| `docs/governance.md` | This document | Workflow / process changes |
| `docs/architecture.md` | Architectural principles | Principles change |
| `docs/design/<n>-...md` | Per-feature design | At step 3 (DESIGN), before code |
| `docs/adr/NNNN-...md` | Architecture decisions | When triggers above met |
| `docs/known-issues.md` | Untestable bugs, gotchas | When found |
| `BUILD_LOG.md` | AI authorship + cost log | Every AI-assisted release |
| `ROADMAP.md` | Where we're going | Major milestones |

---

## Definition of Done

A change is done when **all** are true:

- [ ] Code implements the agreed design
- [ ] Tests added/updated, all tests pass locally
- [ ] Manual smoke test executed where applicable
- [ ] Docs updated: design doc, ADR (if needed), README (if interface changed)
- [ ] Closed-loop verified: `main` after merge is end-to-end runnable
- [ ] Issue checkboxes ticked
- [ ] BUILD_LOG.md updated if AI contributed
- [ ] No secrets, debug prints, or commented-out blocks

If any box is unchecked, the change is not done — even if the code "works."

---

## When to break the rules

These rules exist to make the project survive past the first burst of enthusiasm. But they cost time. Three legitimate reasons to skip steps:

1. **Spike / proof-of-concept** explicitly marked as throwaway, in a separate branch never to be merged
2. **Production incident** where speed matters more than process — but a post-mortem is then mandatory, with retroactive design doc
3. **Trivial changes** (typo, comment, dependency version bump) — single commit, no design phase needed

In all other cases: follow the process. Skipping it always costs more later.

---

## Amendment process

This document is a living agreement. To change it:

1. Open an issue tagged `governance`
2. Propose the change with rationale
3. Discuss in issue comments for at least 24 hours
4. PR updates this file with the change
5. Merge after approval

The current document is binding until amended.
