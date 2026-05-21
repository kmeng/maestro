# Maestro — Claude Code Operating Rules

This file is auto-loaded by Claude Code when working in this repo. It defines how AI contributors must behave when extending Maestro.

For the human-readable project governance, see [`docs/governance.md`](docs/governance.md).
For architectural principles, see [`docs/architecture.md`](docs/architecture.md).

---

## Session-start protocol

Before responding to the user's first substantive request in a fresh session, you MUST:

1. Read the most recent file in `docs/journal/` to learn what the previous session left undone.
2. Run `gh issue list --state open` to see active work.
3. Run `git status` and `git branch --show-current` to verify the working tree is in a clean, expected state.
4. Run `git branch -r | grep -E 'v[0-9]+\.[0-9]+'` to confirm a current dev branch exists on remote. If `main` is the last shipped version and no next dev branch exists, surface this in the synthesis and ask whether to create one **before** taking any branch-creating action. Rationale: feature work routes through the current dev branch, never directly to `main`; a missing dev branch after a release is the gap that causes drift to `main` (see `feedback_branch_workflow`).
5. Synthesize: state where the project sits, what is open, and what you understand the user is now asking. Then ask the user to confirm or correct.
6. Wait for user confirmation before taking any action that creates commits, opens issues / PRs, or pushes to remote.

Compression is allowed when the user's request is read-only or trivial (e.g., "what does X do?"); collapse the synthesis to one sentence.

If `docs/journal/` is empty or missing, skip step 1 and note its absence in the synthesis.

At meaningful session checkpoints — a PR merged, an issue resolved, a major decision made, or when the user signals "wrap up" / "done for today" — offer to append to today's journal entry. Do not infer session end; wait for the user's signal.

---

## Implementation-start protocol

Before writing any code for an implementation task, you MUST:

1. Run `gh issue view <task-issue-number>` and read the full task briefing.
2. Open every link in the task body's "Design references" section — design doc sections (`§design`) and ADRs (`§ADR`) are mandatory reading; the parent epic is mandatory reading.
3. State the implementation plan back to the user, mapping each acceptance criterion in the briefing to "covered by approach X" with one short sentence per criterion.
4. Wait for the user's explicit `go` (or equivalent) before writing code.

When dispatching workers (`coder` / `librarian` / `reviewer` / `scribe`) for an implementation task, **always pass `task_id` (e.g., `"T6.8"`) and `issue_number` (e.g., `64`) as parameters** so the dispatch row is attributed to the right task in `docs/data/dispatch-log.jsonl`. Without these, the row falls through to git-branch inference (works only when the branch matches `(feature|fix|refactor|docs)/<n>-<slug>`) or to the "unattributed" bucket. See ADR-0011.

This protocol applies whenever a request can be traced to an existing task issue. If the user asks for code without referencing an issue, ask which task it corresponds to before proceeding.

The point of mandatory pre-reading: AI implementers start cold every session. Rich, mandatory-reading briefings are the difference between on-target implementation and "close enough but missing constraint X."

---

## Project context

Maestro is an open-source MCP server that orchestrates a heterogeneous AI software team. The orchestrator (Claude Code main session, running on user's subscription) dispatches execution-heavy tasks to cheaper models (DeepSeek, Qwen) via MCP tools. The goal is delivering near-flagship code quality at 10–20% of the cost.

This project is being built by AI as much as by humans. From v0.0.2 onward, every feature is developed using Maestro itself — the project is its own proof of viability.

## Mandatory workflow for any change

You must follow this sequence. Skipping steps is not allowed except for the explicit exceptions in `docs/governance.md` Part 5.

### 1. Analyze before designing

When given a task:
- Restate the user need in your own words
- Identify what's in scope and what's out
- Define acceptance criteria
- **State this back to the user and wait for confirmation before designing**

### 2. Design before coding

For any non-trivial change:
- Write a functional design: what users / callers experience
- Write a technical design: affected modules, interfaces, data shapes, failure modes
- Save it to `docs/design/<issue-number>-<slug>.md`
- If the change has long-term consequences (new dependency, new role, interface change, storage format), write an ADR in `docs/adr/NNNN-title.md`
- **Wait for the user's explicit "approved" before writing code**

### 3. Break tasks into closed loops

Once design is approved:
- Split into tasks of ~30 min – 2 hours each
- Every task must produce a runnable system — `main` is always green
- A task that adds an interface but no caller is forbidden — either include the caller or stub it
- Track tasks as **sub-issues under the parent epic**. Each sub-issue body follows the briefing template in [`docs/governance.md` § Task tracking](docs/governance.md#task-tracking). Checkboxes inline in the parent issue body are no longer used for task tracking.

### 4. Implement one task per PR

- One PR = one task = one closed loop
- Branch naming: `feature/<n>-<slug>`, `fix/<n>-<slug>`, `refactor/<n>-<slug>`, `docs/<n>-<slug>`
- Commit messages follow Conventional Commits (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`)
- PR description links the issue and lists how to verify
- AI authorship attribution mandatory: `Co-authored-by: <model-name> <noreply@<provider>.com>`

### 5. Definition of Done

A change is done only when **all** of:

- [ ] Code matches the approved design
- [ ] Tests pass locally (added/updated as needed)
- [ ] Manual smoke test executed where applicable
- [ ] Design doc and ADR (if any) reflect what was built
- [ ] README updated if public interface changed
- [ ] `main` after merge is end-to-end runnable
- [ ] BUILD_LOG.md updated when AI contributed substantive code
- [ ] No secrets, debug prints, or commented-out blocks

## Hard rules — never violate

### H1. Never commit secrets
Before any `git add` of config, env, or new files: grep for `sk-`, `Bearer `, `password`, `token`, `api_key`. If matched, refuse and report. `.env` and `*.key` must always be in `.gitignore`.

### H2. Never push directly to main
All changes go through PR. The `main` branch is protected by convention.

### H3. Never modify protected docs without explicit instruction
The following are protected; AI may not edit them as a side effect of another task:
- `README.md`
- `CLAUDE.md` (this file)
- `docs/governance.md`
- `docs/architecture.md`
- Any existing ADR in `docs/adr/`

Changes to these require their own dedicated issue and PR.

### H4. Never destructively delete without confirmation
Any `rm`, `git reset --hard`, `git push -f`, file overwrite, or directory removal: state the intent and wait for explicit user approval.

### H5. Never invent file content
If the user says "I'll paste it" or "wait for content," stop and wait. Do not generate content speculatively to "save time."

### H6. Always surface uncertainty
If unsure about a design choice, an API behavior, or a user intent, ask. Confidence is not verification.

### H7. Always report the plan before acting
For any change touching more than a single small file: state what you intend to do, then wait for "go ahead" or equivalent. Don't bundle multiple speculative steps.

## Bug fix protocol

Bugs follow the same workflow with one addition: **a failing test must exist before the fix**.

```
1. Reproduce → write a test that fails
2. Commit the failing test
3. Fix the bug → test passes
4. Commit the fix
5. PR contains both commits in this order
```

Bugs that can't be tested in CI go in `docs/known-issues.md` with defensive code referencing the doc.

## Communication style

- State plans concisely; don't pad with reassurance
- When uncertain, say "I'm not sure" rather than guess
- When a task is ambiguous, ask one focused question, not five
- Report errors with: what failed, why, suggested next step

## When you're stuck

- If a step's instructions conflict with these rules, **rules win** — surface the conflict
- If a tool fails (gh, git, model API), report the exact error and stop
- If the user's request would violate a Hard Rule, refuse and explain
- Never silently skip a step

## Authorship attribution conventions

When making a commit where an AI generated substantive code:

```
Co-authored-by: claude-opus <noreply@anthropic.com>
Co-authored-by: claude-sonnet <noreply@anthropic.com>
Co-authored-by: deepseek-coder <noreply@deepseek.com>
Co-authored-by: qwen-plus <noreply@alibaba.com>
```

Use the model name actually responsible. Multiple co-authors are allowed when multiple models contributed.

Update `BUILD_LOG.md` when releasing a version or completing a milestone, summarizing AI contributions and approximate cost.
