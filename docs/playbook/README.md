# Maestro Orchestration Playbook

Maestro ships you four worker tools (`coder`, `librarian`, `reviewer`, `scribe`) plus
infrastructure to dispatch and audit them. The hard part isn't the tools — it's knowing
**how to drive them well from your orchestrator** (your Claude Code main session).

This playbook is the accumulated know-how for that. Each entry is short, focused, and
written for you to read once and apply. They are not Maestro-project-internal lore; they
are general advice for anyone running an AI software team via Maestro.

## When to read each

Pick the entry that matches the moment you are in:

| You are about to... | Read |
|---|---|
| Write your first spec for `coder` | [dispatch-protocols.md](dispatch-protocols.md) |
| Write tests, or fix a bug your worker introduced | [tests-are-coder-work.md](tests-are-coder-work.md) |
| Send work to `reviewer` and want its verdict to be reliable | [reviewer-context.md](reviewer-context.md) |
| Decide whether to TDD a feature with your workers | [tdd-with-workers.md](tdd-with-workers.md) |
| Notice you are inlining the same upstream contract into a second spec | [contract-sheets.md](contract-sheets.md) |
| Roll out a new worker role and want to validate it before trusting it | [contract-sheets.md](contract-sheets.md) (shadow-mode section) |
| Debug a test failure that looks weird (especially in Python) | [common-traps.md](common-traps.md) |

If you only have time to read one, read [dispatch-protocols.md](dispatch-protocols.md) —
spec quality is the dominant variable in worker output quality.

## How this playbook is meant to be used

You are the orchestrator. Your job is to:

1. **Decide what should be done.** This is unique to your project; no playbook helps here.
2. **Decompose into worker-sized specs.** This is where these guides apply.
3. **Verify and integrate worker output.** Diff verification, running tests, committing.

The playbook helps step 2 and the protocol parts of step 3. It deliberately stays out of
step 1.

## Honest scope

These guides reflect experience routing real implementation work through Maestro's worker
fleet. They are pragmatic, not theoretical. When a guide says "do X" it's because skipping
X has cost real time, not because the advice sounds good.

Equally honest: this is a young playbook. If you find a gap, an entry that doesn't apply,
or a pattern that should be added, the maintainers want to hear about it. The playbook
itself is meant to evolve from your experience too.

## Future direction

A later Maestro release will integrate this playbook into project setup — when you run
`maestro install` or step through the team-composition wizard, relevant pointers will be
written into your project's `CLAUDE.md` so your orchestrator picks them up automatically.
Today the integration is manual: keep this folder visible, and reference the entries from
your own `CLAUDE.md` if you want your orchestrator to consult them by default.
