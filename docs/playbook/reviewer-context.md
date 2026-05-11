# Giving Reviewer the Context It Needs

`reviewer`'s verdict is only as good as the context you send it. Most false positives —
the reviewer says "this will fail" about code that clearly works — trace to context the
reviewer didn't have. This is not a model-capability problem. It is a packaging problem,
and packaging is your job.

This guide covers the two pieces of context that fix the most false-positive flag:
cross-module reference code, and test-results status.

## Reviewer accuracy is a context problem

The first instinct when a reviewer gives a wrong verdict is to wonder whether a different
model would do better. Almost always the answer is no — the issue is that the reviewer
made a reasonable judgement based on what it saw, but what it saw was incomplete.

A common shape:

> The reviewer flags: "code at line 87 doesn't strip whitespace before validation; an
> empty string `'   '` will fail with the pattern error instead of the empty-string
> error."

Looks plausible. But the code calls `RoleEntry(...)`, and `RoleEntry`'s field validator
already strips internally — so the empty-spaces case does produce the empty-string
error, just inside the validator. The reviewer didn't see `RoleEntry`'s definition;
it could only reason about what was in front of it.

Switching models doesn't fix that. Sending the validator's source code into the reviewer
spec does.

## Rule 1: include cross-module reference code

When the code under review depends on the behaviour of another module, **include that
module's relevant code in the reviewer spec**. Not the whole codebase — just the function
or class whose behaviour the reviewed code relies on.

Pattern:

```
## Code under review

```python
<the actual code to review>
```

## Cross-module reference — read-only

The code above depends on `RoleEntry`'s field validators behaving as follows:

```python
<paste the RoleEntry class or just the relevant validators>
```
```

The cost is a few hundred tokens. The benefit is the reviewer not flagging behaviour
already guaranteed elsewhere.

You don't need to include every dependency — only the ones whose behaviour shapes the
review judgement. A good test: ask yourself "could the reviewer reach the wrong verdict
if it didn't know X?" — if yes, include X.

## Rule 2: run tests first, send the results

Before dispatching the reviewer, run the test suite. Send the result summary as part of
the reviewer spec:

```
## Test results

26/27 tests pass. The failing test is `test_member_empty_after_strip_rejected[Cody\n]`
— newlines aren't being rejected. See the validator ordering in the code above; the
strip happens before the control-char check, so `\n` gets stripped silently.
```

This does two things at once:

1. **Removes a class of false positives.** A "this won't work" finding becomes obviously
   wrong when the test exercising that path is passing.
2. **Sharpens true positives.** When a test fails, the reviewer can correlate its
   findings with the actual failure rather than speculating.

If you adopt the test-first protocol (see [tdd-with-workers.md](tdd-with-workers.md)),
you have this for free — the tests already ran before any implementation existed.

## Reviewer verdicts in practice

The reviewer returns one of three verdicts: `pass`, `concerns`, `fail`. Treat them as
follows:

- **`pass`** — proceed. Spot-check one finding if any, but trust the overall verdict.
- **`concerns`** — read each finding. The reviewer is flagging things it noticed but
  didn't escalate. Often these are real and minor.
- **`fail`** — read carefully. A high-severity finding combined with test results that
  contradict it (passing tests on the same path) is a false positive; you can document
  the disagreement and proceed. A high-severity finding combined with a failing test is
  the real thing — fix and re-dispatch.

The point is: don't let reviewer verdicts drive your behaviour blind. The verdict is one
input among several. The other inputs are: do the tests pass, does your own quick read
of the code raise the same concern, does the cross-module reality match what reviewer
assumed.

## When you do override a reviewer verdict

Document why in the commit message or PR body. A line like "reviewer flagged
X-as-high-severity; on review this was a false positive because Y is handled in module Z,
verified by passing test W" preserves the audit trail. Don't silently dismiss findings.

## What this looks like in your CLAUDE.md

```markdown
## When dispatching to Maestro's reviewer

- Run the test suite first; include the result summary in the reviewer spec.
- If the code under review depends on another module's behaviour, paste that module's
  relevant function/class into the spec as a cross-module reference.
- Treat reviewer verdicts as one input among several. Override carefully when test
  results contradict a finding, and document the override.
```
