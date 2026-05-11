# Test-Driven Development with Workers

TDD pays for some kinds of dispatches and not for others. This guide is the decision
matrix and the two-dispatch protocol for cases where you adopt it.

## When TDD pays

TDD is high-leverage when the work being dispatched is **logic-heavy and contract-
specifiable**:

- Data models and validators
- I/O helpers with state-driven return shapes (e.g., three-state load → present/absent/invalid)
- Dispatchers, resolvers, state machines
- API endpoints with well-defined status-code contracts
- Pure functions where input → output relationships are enumerable

For this kind of work, a test list **is** the spec. Writing the tests first forces you to
specify the contract precisely, and the implementation phase becomes "make these pass" —
which is unambiguous to a worker.

The biggest payoff: schema-mismatch bugs surface immediately. If coder misreads the data
model (e.g., uses attribute access on a dict-typed field), the tests fail on the very
first run rather than later, in a different test, with a confusing trace.

## When TDD doesn't pay

TDD is low-leverage or counter-productive when:

- **The output is templates or HTML rendering.** Tests can only assert string presence,
  which is essentially the same work as writing the template. You end up writing the
  template twice.
- **The change is simple wiring.** One-line additions to a module's exports, registering
  a route, adding a constant. The TDD overhead exceeds the work itself.
- **The deliverable is documentation, prose, or smoke scripts.** There is no "contract"
  to express as tests — the artifact is the test.

For these, write tests after, alongside the implementation, in a single dispatch.

## The 2-dispatch protocol for TDD cases

When you adopt TDD for a dispatch, the protocol is:

**Dispatch 1 — tests only.** The spec is:
- The list of test names + one-line behaviour descriptions
- Any helper / fixture definitions the tests should share
- An explicit "do NOT write production code in this dispatch — only tests"
- Any cross-module reference code the tests need to import (data models from earlier
  tasks, etc.)

Coder produces just the test file. You save it, run it, and verify:

- Every test fails (correctly — `ImportError` is fine if the production module doesn't
  exist yet; `AssertionError` is even better)
- Failure messages are meaningful (not e.g. silent skips)

If a test "passes" against a module that doesn't exist, the test is wrong — re-dispatch
to fix the test before moving to the implementation.

**Dispatch 2 — production code.** The spec is:
- The test file (the contract)
- The constraints (no Pydantic v1, Python 3.10+, etc. — usual hard constraints)
- An explicit "the tests in `tests/test_xxx.py` are the contract; make them all pass
  without modifying them"
- Any reference code the implementation needs

Coder produces the production module. You run the tests. All pass → land. Some fail →
either re-dispatch with the specific failures called out, or accept and document a test
adjustment if the test was wrong.

## What the protocol costs

Two dispatches instead of one. Each dispatch is smaller (the spec for each is more
focused), so the per-dispatch worker time roughly halves. Net worker cost: comparable.

The orchestrator cost goes down notably, because the implementation phase doesn't need
the orchestrator to spot bugs by hand — bugs show up as failing tests. Less orchestrator
work means less flagship-model spend.

## What the protocol catches

Bugs the protocol catches reliably:

- **Schema misunderstanding.** Wrong attribute access, wrong method name, wrong shape of
  return value — all become test failures on first impl-dispatch.
- **Missing behaviour.** A spec that listed test_X but the implementation forgot it —
  test_X fails immediately.

Bugs the protocol does not catch (these need other defences):

- **Format errors in the worker's output itself.** Coder occasionally returns an empty
  output block or malformed structured response. Re-dispatch with a format reminder.
- **Cross-cutting decisions** that aren't expressible as a test. Whether to use atomic
  writes vs append-only logging, whether to log to stderr or a file — these are design
  choices that need to be in the prose spec.
- **Implementation drift in modify-existing-file dispatches.** Tests pass but the worker
  also rewrote a function it wasn't supposed to touch. The defence here is diffing
  worker output against the original (see [dispatch-protocols.md](dispatch-protocols.md)).

## A pragmatic mix

You will not run TDD on every dispatch, and you should not. The rule of thumb:

> If the task has a precise input/output contract you can write as a test list before
> implementation, use TDD. Otherwise, write tests alongside.

Most projects end up running TDD on roughly half their dispatches — the half doing
data-shape and logic work. The other half (UI, glue, docs, smoke) gets test-after.

## What this looks like in your CLAUDE.md

```markdown
## TDD with Maestro

- For logic-heavy tasks (data models, validators, dispatchers, I/O, API contracts),
  use the 2-dispatch TDD protocol: tests first, then implementation, with the test file
  as the implementation spec.
- For templates, simple wiring, docs, and smoke scripts: write tests alongside in a
  single dispatch.
- When in doubt, ask: "can I express the acceptance criteria as a test list before
  implementation?" If yes, TDD pays.
```
