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
                → tracked as sub-issues under the epic; each
                  sub-issue body follows the briefing template
                  (§ Task tracking)
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

## Task tracking

Tasks live as **sub-issues under their parent epic**. GitHub's sub-issues feature (GA 2025) provides parent→child issue hierarchy natively — the parent issue auto-displays "N of M sub-issues completed," each sub-issue has its own id and can be closed independently by `Closes #N` in a PR.

### Briefing template

Each sub-issue body follows this template. The body is the *task's contract*; PRs satisfy it.

````markdown
## Goal

[One paragraph: what this task achieves once merged.]

## Design references (mandatory reading)

- §design: [docs/design/<file>.md — § Section name]
- §ADR: [docs/adr/<file>.md — § Section name]
- Parent epic: #<epic-issue-number>

## Scope

What this task does:
- [...]

What this task explicitly does not do:
- [...]

## Acceptance criteria

- [ ] [Enumerated, testable criterion 1]
- [ ] [Enumerated, testable criterion 2]
- ...

## Test plan

- Unit: [test file paths and what they cover]
- Smoke: [manual verification steps where applicable]

## Estimate

~Nh

## Dependencies

- None / #<other-task> / [list]
````

### Creating sub-issues

`gh` CLI (as of 2.89.0) does not have a `gh sub-issue` subcommand. Sub-issue creation uses `gh api` against the REST endpoint `POST /repos/{owner}/{repo}/issues/{parent}/sub_issues` with the child issue's internal `id` (not its number). A small helper script (e.g., `scripts/create_subissue.sh`) is the recommended path; the script body is workflow tooling, not governance content.

### What checkboxes are still for

Checkbox lists inside an issue or design-doc body are still used for **acceptance criteria** within a single sub-issue's briefing, and for **Definition of Done** within a single PR's description. They are no longer used for task lists across multiple PRs — that role belongs to sub-issues.

---

## Branch and commit conventions

### Branches

This project distinguishes **remote (origin)** and **local** branches sharply.

#### Remote (origin)

Origin carries only release branches:

| Branch | Purpose |
|---|---|
| `main` | The released line. Updated only via merged release PRs. |
| `v0.X.Y` | Active release-integration branch. Receives the next release's commits. Created from `main` at the start of a release window; deleted from origin after its release ships and `main` advances. |

No feature, fix, or task branches appear on origin. The remote stays uncluttered: humans browsing origin see only the release lineage.

#### Local

Local branches are unrestricted in number and name. Suggested conventions (not enforced):

| Prefix | Use for |
|---|---|
| `feature/<n>-<slug>` | issue-aligned work |
| `fix/<n>-<slug>` | bug fix |
| `refactor/<n>-<slug>` | internal restructure |
| `docs/<n>-<slug>` | documentation only |
| `task/<n>-<step>` | sub-step within a larger feature |

`<n>` is the GitHub issue number. `<slug>` is short kebab-case. These names never appear on origin.

#### Push protocol

A local feature or task branch merges (preferred: `--no-ff`) into the local release branch (`v0.X.Y`). Only the release branch is pushed. Local sub-branches are deleted (`-D` after squash semantics, `-d` after non-squash) once merged.

#### PR protocol

The only PR that appears on origin is the release PR (`v0.X.Y → main`). Feature-level review happens locally — in commit history of the release branch, in design docs under `docs/design/`, and in the maintainer-AI conversation transcripts.

#### Historical note

In the v0.0.2 cycle (issue #6), the project briefly used a three-tier model: feature branches (`feature/6-env-loading`) were pushed to origin and reviewed via PR (`feature/* → v0.0.2`). The lived experience clarified that this added remote noise without payoff for solo / AI-paired work. The current policy supersedes that.

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

- One PR = one closed loop = one task sub-issue closed
- PR description must include:
  - `Implements: #<sub-issue-number>` (the task being closed)
  - `Closes #<sub-issue-number>` on its own line in plain prose (per the auto-close phrasing rule below)
  - `Design citation: docs/design/<file>.md — § Section` (the design section being implemented)
  - **Acceptance-criteria checklist** copied from the sub-issue body, with each item ticked and a one-line note on how it is verified
  - Test results / smoke output (paste the relevant lines)
- Squash-merge to main; no merge commits in main
- PR > 400 lines: justify in the description or split

In the current project phase, "PR" practically refers to the release PR (`v0.X.Y → main`). Feature-level closed loops happen in local commits of the release branch and don't surface as separate origin PRs (see the branch policy above). The "one closed loop per PR" rule still applies — at the release granularity.

In solo phase, the maintainer reviews their own PRs after a 24-hour cooling-off period, OR explicitly self-approves with rationale in the PR description.

For PR descriptions that should auto-close an issue on merge, place the closing keyword (`Closes`, `Fixes`, `Resolves`) on its own line in plain prose, not inside a markdown heading, list, or code block. Auto-close only triggers when the PR base is the default branch (`main`).

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

### Bug as an independent issue

A bug is filed as its **own independent issue**, not as a sub-issue of any task. The bug issue body includes:

- Provenance: `Found while implementing #<task-issue>` or `Regression in #<task-issue>` (link back to the task or epic where the bug originated, when known).
- Reproduction steps.
- The expected vs actual behavior.
- A reference to the failing test once it exists (per the protocol above).

The PR that fixes the bug uses `Closes #<bug-issue>` on its own line in plain prose, the same auto-close phrasing rule as for tasks.

When labels are introduced, bug issues carry the `bug` label.

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
| `docs/journal/<YYYY-MM-DD>.md` | Per-session run log; cross-session shared memory | Each working session, at session end |
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
