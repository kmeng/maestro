# Tests Are Coder's Work, Not Yours

The temptation: a test is small, you can knock it out in 30 seconds in your orchestrator
session. The reality: tests are code, and code goes to `coder`. Every test you write in
your orchestrator is dogfooding leaking out the seams.

This guide is short because the rule is simple. The point is to make it explicit so you
notice when you are about to break it.

## The rule

Every test — initial test, follow-up test, regression test, bug-fix test, integration
test — is dispatched to `coder`. The orchestrator's only role with tests is:

1. Enumerate the tests in the spec (one line each)
2. Verify the result (run the tests; check they cover the listed cases)
3. Land the diff

The orchestrator does not write the test bodies. Not even quick ones. Not even one-liners.

## Why the rule is easy to break

Three plausible-sounding reasons to write a test yourself, all of which add up to a
significant token leak over time:

**"I'll just add a quick test for this new edge case."** The fastest path feels like
writing it inline. But you are paying flagship-model prices to write code that costs
your worker fleet ~5% as much. Five "quick tests" a week becomes hundreds of dollars a
year, and meanwhile your dogfooding cost story is quietly false.

**"The worker's tests had a bug; I'll just fix it."** This is the same pattern wearing a
different hat. The fix to a bug in coder's test is a re-dispatch to coder with a sharper
spec — "the previous attempt's test 18 contained a logically contradictory assertion;
correct it as follows". The cost is one more worker round-trip; the benefit is keeping
the dogfooding edge sharp.

**"This test requires understanding the codebase across files; coder can't do that."**
If your dispatch needs cross-file context, send the cross-file context. The fix is in the
spec, not in taking the work back. See [reviewer-context.md](reviewer-context.md) for
how to package cross-module context for workers.

## When coder's test output has a bug

The instinct is to grab the diff and patch it. Resist. The cheaper path is almost always:

1. Save coder's output as-is to your branch
2. Run the tests and observe the failure
3. Compose a follow-up dispatch: "the previous output's `test_X` does Y; correct to Z. The
   rest of the file is fine — return only `test_X` rewritten."
4. Splice the corrected test into the file

The follow-up dispatch is cheap (~5k tokens) and keeps the dogfooding loop closed. Doing
the fix yourself feels faster but compounds.

## When the original spec didn't ask for tests, and now you need them

Same protocol. Compose a new dispatch with the test enumeration and the existing
production code as reference. Coder writes the tests. You verify and land.

The trap-pattern to avoid: "I'll write the integration tests myself since the original
spec didn't cover them." Once integration tests are 200 lines of orchestrator-written
code, you've replicated a small worker's job at flagship-model cost.

## The honest exception

There are situations where the orchestrator legitimately writes test-shaped code:

- **A one-line assertion check during exploration**, before any commit, to verify
  something interactively. Throwaway, not committed.
- **A debugging probe** added mid-investigation, removed before commit.

If it's going to be committed and live with the rest of the test suite, dispatch.

## What this looks like in your CLAUDE.md

```markdown
## Testing with Maestro

- All tests — initial, follow-up, bug-fix, regression, integration — go to coder. Do not
  write committed test code in this orchestrator session.
- When a worker-produced test has a bug, re-dispatch to coder with a sharper spec rather
  than patching it inline.
- The orchestrator's role with tests is: enumerate them in the spec, run them, verify
  coverage, land the diff.
```
