# Maestro Session Journal

Each calendar day of work on Maestro gets one Markdown file here, named `YYYY-MM-DD.md`. The journal is the project's running log — the place where we record what was done, what was decided, what was deferred, and what a fresh Claude Code session needs to know to continue.

This is not a TODO list. It is not a changelog. It is the cross-session **shared memory** layer between sessions, between collaborators (human and AI), and eventually between MCP workers.

## Why this exists

- `CLAUDE.md` and project memory hold *stable rules*. They don't move day to day.
- `BUILD_LOG.md` summarizes per-release AI authorship, written when a release ships.
- `docs/design/<n>-<slug>.md` captures the design of one specific feature or change.
- GitHub issues track discrete work items with their own threads.

None of those answer the question: *"What is the state of work right now, and what was the most recent thinking about it?"* That gap is what the journal fills.

## When to write

Write a session entry at meaningful checkpoints — not continuously, not on every commit. Triggers include:

- A PR has merged
- An issue has been resolved or deferred
- A material decision has been made (architectural, process, scope)
- The user signals "wrap up" / "done for today" / "we'll continue tomorrow"

Claude does not infer session end. The maintainer triggers a journal write explicitly. (See `CLAUDE.md` "Session-start protocol" for the read side; the write side is the same protocol in reverse.)

## When to read

At the start of every fresh Claude Code session, before responding to the user's first substantive request. This is part of the session-start protocol in `CLAUDE.md`. Read the most recent entry; that gives you the immediate state. Read further back only if the most recent entry refers to earlier context.

## File format

```markdown
# YYYY-MM-DD

## Session N — <start time> → <end time> <tz>

**Done**
- Bullet list of what was completed today, with `#issue` and `#PR` links.

**Decided**
- Bullet list of decisions made today (architecture, scope, policy).

**Deferred**
- Bullet list of what was *not* done, with reason. If a follow-up issue exists, link it.

**Handoff for next session**
- Free-form prose covering: branch state, working tree state, open issues
  worth attention, any "mental thread" the next session should pick up,
  watchpoints carried from earlier design docs.

**Process learnings** (optional — only if a durable lesson surfaced)
- Bullet list of process / workflow lessons. If terse, add to project memory; if detailed enough to deserve a permanent home, also lift into `docs/governance.md` or `CLAUDE.md` via a dedicated PR.

**Costs** (optional — when dogfooding starts)
- Token counts and dollar spend for any `cheap_code_gen` dispatches.
```

If a single calendar day has multiple sessions (rare), append additional `## Session 2 — ...` blocks to the same date's file. Do not split a single day across multiple files.

## Commit policy

- Journal entries live in `docs/journal/` and are committed on whatever local branch is active when the entry is written. They reach `main` through the standard release flow (local task branch → local release branch → release PR).
- Conventional commit message: `journal: <YYYY-MM-DD> session N wrap` for a session-end entry, or `journal: <YYYY-MM-DD> update` for a mid-session amendment.
- A journal commit does not require its own issue or design doc — it is the project's running log.
- Do not amend journal entries from previous days to revise history. If a previous entry was wrong, write a correction in today's entry and reference the date.

## Anti-patterns

- **Treating it as a TODO list.** Use issues for work items. The journal records what *happened* with them, not what's pending.
- **Writing for an external audience.** This is internal state continuity, not a blog post. Skip background context that's already obvious from the project.
- **Padding entries with meta-commentary.** "We had a productive session today" — delete. Concrete actions, decisions, and handoff notes only.
- **Restating governance rules in the journal.** Rules belong in `docs/governance.md` and `CLAUDE.md`. Journal references rules by link.
- **Backdating.** If a session crossed midnight, file it under the date the bulk of the work happened. Do not retroactively split.
- **Vague handoff notes.** "Continue working on X" is useless. Better: "We're at commit `abc1234` on `v0.0.X`; the open question is whether to do Y or Z; my last thinking was Z because of W."
