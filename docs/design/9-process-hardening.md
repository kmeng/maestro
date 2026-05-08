# Design: process v0.0.2 hardening — journal, branch policy, session-start protocol

**Issue**: #9
**Status**: draft

## Problem

After v0.0.2 shipped (issue #6), three governance gaps remain:

1. **No cross-session memory layer**. Chat context disappears at session boundary. CLAUDE.md and project memory hold *stable rules*, not *current state of work*. When the maintainer or a future contributor starts a new Claude Code session, they have no canonical place to read "what's in progress, what's deferred, what's decided".
2. **`docs/governance.md` does not describe the actual branch policy used**. The lived policy clarified during v0.0.2 — *origin carries only release branches; local branches are unrestricted* — is not documented. The current `docs/governance.md` "Branch and commit conventions" table conflates remote and local concerns.
3. **`CLAUDE.md` has no protocol for how a fresh session enters the project**. Every new session starts cold; the user pays the cost of re-establishing context. With (1) solved, this becomes a simple "read the journal, list open issues, ask to confirm" protocol.

This design closes all three at once.

## Out of scope

- v0.0.3 design or any feature work
- Branch cleanup of stale remote branches (handled separately as ops cleanup; not this PR)
- Updates to issue #2 / #3 descriptions (handled separately as ops cleanup; not this PR)
- Tooling around journal (e.g. a script to bootstrap today's entry). Manual append is fine for now; revisit if friction.
- Auto-detection of "session end" — Claude writes the journal when the maintainer signals end-of-session, not via inference.

## Functional design

### A. Session journal — what humans (and Claude) see

A new directory `docs/journal/` with:

- `README.md` — explains the format, write/read protocol, anti-patterns
- `YYYY-MM-DD.md` — one file per calendar day; multiple sessions in a day append additional `## Session N` blocks

A typical entry contains:

```markdown
# 2026-05-08

## Session 1 — 14:00 → 18:30 CST

**Done**
- Closed issue #X via PR #Y (one-line summary)
- Renamed issues #1 / #2 / #3 to drop noisy prefix

**Decided**
- Remote-only-release-branches policy (codified in #9)
- Defer v0.0.3 inception to next session

**Deferred**
- v0.0.3 candidate features (issue: TBD next session)

**Handoff for next session**
- Branch state: on `v0.0.2`, clean working tree
- Open issues: #2 (dogfooding manifesto, tracking), #3 (v0.1 roadmap, tracking), #9 (process hardening, will be closed by release PR)
- Mental thread: v0.0.3 should be the first dogfooding-active release; pick a candidate worker role to add (cheap_explain?)
- Watchpoints carried: OPEN-1 / OPEN-2 / OPEN-3 / OPEN-4 in `docs/design/6-env-loading.md`; OPEN-5 resolved by this PR

**Process learnings**
- (optional, only when there's something durable)
```

### B. Governance branch policy — what humans see

`docs/governance.md` "Branch and commit conventions" section is rewritten to make explicit:

- Remote (origin) carries only release branches
- Local branches are unrestricted
- Push protocol, PR protocol, branch naming convention (local-only)

The Pull Request rules section is lightly updated to clarify that "PR" in this project's vocabulary now refers to the release PR (`v0.0.X → main`), with feature-level review happening locally.

The Documentation rules table gains a new row for `docs/journal/`.

### C. Session-start protocol — what humans see

`CLAUDE.md` gains a new section near the top, before "Mandatory workflow for any change". The protocol is:

When a new Claude Code session opens this repo, before responding to the user's first request, Claude:

1. Reads the most recent file in `docs/journal/` (most recent calendar date with content)
2. Runs `gh issue list --state open` to see active issues
3. Runs `git status` and `git branch --show-current` to verify working state
4. Reports a brief synthesis to the user: "Last session left us at <state>. Open issues: <list>. Working tree: <state>. You asked: <user's request>. Should I proceed, or is my understanding off?"
5. Waits for user confirmation/correction before starting work

If `docs/journal/` is empty or missing, Claude skips step 1 and notes its absence in the synthesis. If the user's request is trivial (e.g., "what does X do?"), Claude can compress the protocol to a single line.

Symmetrically, at meaningful end-of-session checkpoints, Claude offers to update today's journal entry with what was done and what's deferred. The maintainer triggers this explicitly ("update the journal" / "wrap up"); Claude does not infer session end.

## Technical design

### A. Journal — files, format, commit policy

**Directory and naming**

```
docs/journal/
  README.md                    (format spec; this PR creates)
  2026-05-08.md                (today's entry; this PR creates)
  2026-05-09.md                (next session creates, etc.)
```

File name: `YYYY-MM-DD.md` (UTC or maintainer's local — convention: maintainer's local, since journal is human-first).

**Required sections per entry** (in order):

- `# YYYY-MM-DD` (h1, just the date)
- `## Session N — <start> → <end> <tz>` (h2, one per session)
  - `**Done**` (bullet list, with issue/PR/commit links)
  - `**Decided**` (bullet list — design choices, policy changes)
  - `**Deferred**` (bullet list — what was *not* done and why; pointer to follow-up issue if filed)
  - `**Handoff for next session**` (free-form prose, the most important section)

**Optional sections**:

- `**Process learnings**` (only when a durable lesson surfaced; otherwise omit)
- `**Costs**` (when dogfooding starts — token counts, dollar spend per dispatch)

**Commit policy**

- Journal entries are committed on whatever local branch is active. They reach `main` through the same release flow as code/docs.
- A typical day's last commit on the release branch is `journal: <YYYY-MM-DD> session N wrap`.
- Journal commits do not require a separate issue or design doc — they are the project's running log, like build artifacts of work but human-readable.

**Anti-patterns the README should warn against**

- Treating journal as a TODO list (use issues for that)
- Writing for an external audience (it's for the project's own state continuity)
- Padding entries with meta-commentary or restating governance rules
- Backdating entries; if a session crossed midnight, write it under the date the bulk of work happened

### B. Governance edits — section by section

**Section "Branch and commit conventions"** — full rewrite of the `### Branches` subsection. Replace the current 5-row prefix table with:

```markdown
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

A local feature or task branch merges (preferred: `--no-ff`) into the local release branch (`v0.X.Y`). Only the release branch is pushed. Local sub-branches are deleted (`git branch -D` after squash semantics, or `-d` after non-squash) once merged.

#### PR protocol

The only PR that appears on origin is the release PR (`v0.X.Y → main`). Feature-level review happens locally — in commit history of the release branch, in design docs under `docs/design/`, and in maintainer-AI conversation transcripts.

#### Historical note

In the v0.0.2 cycle (issue #6), the project briefly used a three-tier model: feature branches (`feature/6-env-loading`) were pushed to origin and reviewed via PR (`feature/* → v0.0.2`). The lived experience clarified that this added remote noise without payoff for solo / AI-paired work. The current policy supersedes that.
```

**Section "Pull Request rules"** — light edit. The line "One PR = one task = one closed loop" stays valid, but its meaning evolves: in solo / pre-team phase, "one PR" practically means "one release PR per release". Add a clarifying sentence:

```markdown
In the current project phase, "one PR" practically refers to the release PR. Feature-level closed loops happen in local commits of the release branch; they don't surface as separate origin PRs.
```

**Section "Documentation rules" table** — add a row for `docs/journal/`:

```markdown
| `docs/journal/<YYYY-MM-DD>.md` | Per-session run log; cross-session memory | Each working session, at session end |
```

### C. CLAUDE.md edits — exact placement and content

Insert a new top-level section between the intro/links block and `## Project context`:

```markdown
## Session-start protocol

Before responding to the user's first substantive request in a fresh session, you MUST:

1. Read the most recent file in `docs/journal/` to learn what the previous session left undone.
2. Run `gh issue list --state open` to see active work.
3. Run `git status` and `git branch --show-current` to verify the working tree is in a clean, expected state.
4. Synthesize: state where the project sits, what is open, and what you understand the user is now asking. Then ask the user to confirm or correct.
5. Wait for user confirmation before taking any action that creates commits, opens issues / PRs, or pushes to remote.

Compression is allowed when the user's request is read-only or trivial (e.g., "what does X do?"); collapse the synthesis to one sentence.

If `docs/journal/` is empty or missing, skip step 1 and note its absence in the synthesis.

At meaningful session checkpoints — a PR merged, an issue resolved, a major decision made, or when the user signals "wrap up" / "done for today" — offer to append to today's journal entry. Do not infer session end; wait for the user's signal.
```

The rest of `CLAUDE.md` is unchanged. The "Mandatory workflow for any change" section already covers the ANALYZE → DESIGN → APPROVAL → IMPLEMENT pattern; the session-start protocol is the entry point that ensures this workflow starts from a known state.

## Task breakdown

All work happens on local task branches off `v0.0.2`, merged back into local `v0.0.2` with `--no-ff`. Only `v0.0.2` is pushed. Single release PR `v0.0.2 → main` closes #9.

### Task 1 — establish journal infrastructure

Local branch: `task/9-journal`

Files:
- `docs/journal/README.md` (new) — format spec per "Technical design A"
- `docs/journal/2026-05-08.md` (new) — today's entry, populated incrementally; final fill-in is the last task

Local commit message: `docs(#9): introduce session journal mechanism`

Closed loop: after merge, `docs/journal/` exists with a working format spec and a stub for today.

### Task 2 — governance.md branch policy rewrite

Local branch: `task/9-governance`

Files:
- `docs/governance.md` — rewrite `### Branches` subsection per "Technical design B"; light edit to "Pull Request rules"; add row to "Documentation rules" table

Local commit message: `docs(#9): document remote-only-release-branches policy in governance`

Closed loop: after merge, governance accurately describes how we work.

⚠️ H3 note: `docs/governance.md` is a protected doc. This task IS the dedicated change to it (per H3); not a side effect of another task.

### Task 3 — CLAUDE.md session-start protocol

Local branch: `task/9-claude-md`

Files:
- `CLAUDE.md` — insert new "## Session-start protocol" section per "Technical design C"

Local commit message: `docs(#9): add session-start protocol to CLAUDE.md`

Closed loop: after merge, fresh sessions have an explicit entry protocol.

⚠️ H3 note: `CLAUDE.md` is a protected doc. This task IS the dedicated change to it (per H3); not a side effect of another task.

### Task 4 — fill in today's journal + cross-reference OPEN-5

Local branch: `task/9-journal-fill`

Files:
- `docs/journal/2026-05-08.md` — fill in the full entry covering today's work (issue rename, body update, bootstrap branch deletion, this entire issue #9 effort)
- `docs/design/6-env-loading.md` — append a note to OPEN-5 marking it resolved by issue #9

Local commit message: `docs(#9): fill 2026-05-08 journal; mark OPEN-5 resolved`

Closed loop: after merge, the journal has a real first entry exemplifying the format, and the cross-reference back to issue #6's watchpoint is closed.

### After all tasks merged

- Push `v0.0.2` to origin
- Open release PR `v0.0.2 → main` with title `release: v0.0.2 — process hardening (#9)` (or similar)
- Body: standalone-line `Closes #9.` per the auto-close phrasing rule

## Acceptance criteria

After release PR merges to `main`:

- [ ] `docs/journal/README.md` exists, readable, names format and commit policy
- [ ] `docs/journal/2026-05-08.md` exists with at least one filled-in session entry covering today's work
- [ ] `docs/governance.md` `### Branches` subsection describes remote-only-release-branches policy with explicit local/remote distinction
- [ ] `docs/governance.md` documentation rules table includes `docs/journal/` row
- [ ] `CLAUDE.md` has a `## Session-start protocol` section before `## Project context`
- [ ] `docs/design/6-env-loading.md` OPEN-5 marked resolved (with link back to #9)
- [ ] Origin remote branches: only `main` and (depending on timing) any current `v0.X.Y` — no feature / task / fix branches
- [ ] A fresh Claude Code session opening this repo, given a non-trivial request, runs the session-start protocol within its first 2-3 tool calls and produces a synthesis the maintainer can confirm or correct

## Open questions

Recording for future, not blocking this PR.

- **OPEN-1**: Journal entries today are written by Claude based on the maintainer's "wrap up" signal. If sessions become longer / more frequent, consider a script (`bin/journal-stub`) that templates a stub for today. Current friction is low; revisit when it isn't.
- **OPEN-2**: Journal format spec lives in `docs/journal/README.md`. If the format evolves (e.g. needing a `**Costs**` section once dogfooding starts), update the README in the same PR as the format change. Don't let the spec drift from actual entries.
- **OPEN-3**: Multiple Claude Code sessions running in parallel (e.g. if the maintainer opens a second session in another worktree) could lead to journal merge conflicts. Pragmatic punt: rare in solo mode; revisit when it actually happens. The fix would be either time-stamped sub-sessions or one-file-per-session naming.
- **OPEN-4**: CLAUDE.md edits expand its size. If it crosses ~200 lines, consider splitting into `CLAUDE.md` (operational rules) + `docs/governance.md` (policy detail). Currently fine.
