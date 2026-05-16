# Contract Sheets — One Source of Truth for Shared Upstream

When two or more sub-tasks in the same scope depend on the same upstream code — the
same Pydantic models, the same function signatures, the same JSON shape — you have a
choice. Inline the contracts into each task's spec, paying the cost three times. Or
sink them into one document the specs reference. The second is a contract sheet.

This entry is the convention for writing and maintaining contract sheets, plus the
shadow-mode protocol for rolling out a worker role that consumes them.

## What a contract sheet is

A contract sheet lives at `docs/contracts/<scope>.md`. The scope is usually an epic
(`docs/contracts/epic-3.md`) or a long-lived subsystem boundary (`docs/contracts/
dispatch-log.md`). The sheet contains, verbatim from the production code:

- Model definitions (Pydantic classes, dataclasses, TypedDicts) with all fields.
- Function signatures with type hints intact.
- Failure contracts for every public function (what raises, what doesn't, what
  returns sentinel values).
- JSON shapes, route paths, event names — anything a caller assumes about the
  upstream that isn't already obvious from the function signature.
- Last-updated date and the PR or journal entry that produced the most recent edit.

The canonical example is [`docs/contracts/epic-3.md`](../contracts/epic-3.md): 10
sections covering event models, the reader and writer, the dispatcher's three-state
branching, the SSE endpoint, shared UI conventions, the templates name-collision
gotcha, and a "deferred to next version" section. Read it once before drafting your
own — the rhythm transfers more easily than any prose description.

## When to create one

The trigger is concrete: **at the moment a second sub-task in the same wave is about
to inline the same upstream contract a previous task already inlined**, stop and
sink it. The first task pays for full-file inline reading; everyone after points at
the sheet.

Specifically:

- Two or more sub-issues' coder specs would each reproduce the same model definitions
  → sheet.
- Two or more reviewer payloads would each carry the same function signatures →
  sheet.
- The same `feedback_verify_paths_before_spec` grep would be repeated by the
  orchestrator three sessions in a row → sheet.

Do not create a contract sheet preemptively. The cost of an unused sheet is the
maintenance burden — it falls out of sync silently, and a stale sheet is worse than
no sheet (it pretends to be authoritative). Wait until the second caller's value is
obvious.

## Content rules

Five rules, in order of importance:

1. **Verbatim from source.** Copy the function signature character-for-character.
   Do not "clean up" docstrings, drop unused imports for clarity, or summarize a
   long Pydantic model with "and 4 other fields". The whole value is that a coder
   spec can paste the sheet's quote into a worker dispatch with zero re-verification.

2. **Failure contracts are explicit.** Every public function gets a "Failure
   contract" line enumerating: what raises which exception, what returns a
   sentinel like `None` or `[]`, what swallows errors silently. If the upstream
   author left it ambiguous, the sheet's job is to make it not-ambiguous —
   including saying "raises on permission errors, returns `[]` on missing file"
   in plain words. Memory entry `feedback_api_failure_contract_explicit` applies.

3. **Gotchas have a date and a PR reference.** When a future reader hits the
   gotcha, they need to know it was real, not theoretical. Format: "**W5 pitfall**:
   any test that constructs an event with `role="junior"` silently fails Pydantic
   validation." with a link to the journal entry or PR where the pitfall was
   discovered. Without the reference the gotcha eventually reads as folklore.

4. **Last updated** at the bottom. Date + the close milestone (`2026-05-12 (W5
   close)`). When this date is older than the most recent change to any file the
   sheet quotes, the sheet is stale until verified.

5. **No task-specific guidance.** The sheet describes the upstream, not what any
   particular task should do with it. Lines like "T8.3 must call this with
   `mode='strict'`" belong in T8.3's spec or briefing, not the sheet. Anti-pattern
   sketched below.

## Update protocol

Code change and sheet update land in the **same PR**. This is the one rule whose
violation produces stale sheets immediately and at scale, so it is non-negotiable:

- Modify a function signature → update the sheet entry in the same diff.
- Add a new event type, a new JSON field, a new route → append a section.
- Rename a function → search-and-replace inside the sheet, verify all callers.
- Deprecate or remove something → strike from the sheet, note it under "Deferred"
  or "Removed" with a date.

When a PR touches upstream and does not update the sheet, the reviewer's job is to
catch it. Reviewer skill prompts may want a default check: "if this diff modifies
any function whose signature appears in a `docs/contracts/*.md` file, the sheet
must be updated in this PR."

When you write a spec that quotes the sheet, include `last verified <commit-sha>`
or `last verified <YYYY-MM-DD>` in the spec text. This caps the staleness window
at the time of the dispatch — if the sheet has drifted since that commit, the
verifier (mcp__maestro__verifier, shipped in Epic 8) flags it.

## Anti-patterns

Avoid these. Each has cost something real:

- **Summarizing the upstream.** "The event model has the usual fields plus a
  `cost` breakdown." Now the coder has to infer what "usual" means, and gets it
  wrong. Verbatim or no entry; the middle ground is the worst of both.

- **Including task-specific guidance in the sheet.** "When implementing the new
  alert role, pass `severity='critical'`." This is briefing content. It pollutes
  the sheet, and worse, future tasks reading the sheet think the line still
  applies to them.

- **Letting the sheet describe what the code "should" do.** A contract sheet is
  descriptive, not prescriptive. If the upstream returns `None` on missing-file
  when the sheet author thinks it should raise, the sheet documents the actual
  `None` behavior — and opens a separate issue for the change. Do not lie about
  the upstream.

- **Quoting paraphrases of comments.** The verbatim contract is about code
  surface (signatures, types, returned shapes). Quoting docstring prose is fine,
  but only the parts that constrain caller behavior. Marketing-style docstrings
  ("This function elegantly handles...") have no place.

- **Forgetting the "Update protocol" rule under deadline pressure.** The moment
  the sheet falls one PR behind, callers stop trusting it. Two PRs behind, they
  stop reading it. Always update in the same PR — there is no separate "fix
  contract sheets" sweep that ever happens.

## Shadow-mode protocol — for rolling out a new worker role

Contract sheets pair naturally with new worker roles, since the same scope produces
both the sheet (so callers can reference it) and the worker that consumes it (so the
sheet's value compounds). When a new worker role is introduced — `verifier`,
`spec-writer`, anything coming after — the rollout is staged via shadow mode.

### Phase 1 — Hand-draft + dispatch in parallel

For the first 1–2 waves where the new worker is used in production, the orchestrator
**both**:

1. Hand-drafts the artifact the worker would produce, as if the role didn't exist.
2. Dispatches the worker against the same inputs.

The two outputs are compared per task. The orchestrator merges the hand-drafted
version (which they trust) and treats the worker output as a sample under evaluation.

### Phase 2 — Per-task comparison

Three comparison dimensions, in order of importance:

- **Correctness.** Did the worker produce something usable? Did it miss any
  acceptance criterion the hand-drafted version covered?
- **Drift.** Where did the worker output differ from the hand-drafted version,
  and is the difference an improvement, a regression, or a wash?
- **Coverage.** Are there inputs the worker handles well that the orchestrator
  was likely to under-specify? (Shadow mode exists partly to surface what the
  worker is better at, not just to verify it isn't worse.)

Capture the comparison in the wave's journal entry. Two or three sentences per
task. Do not try to score it — the comparison is qualitative.

### Phase 3 — Promotion or iteration

After 1–2 waves of shadow comparisons:

- **Clean comparisons → promote.** Update `feedback_shadow_mode_active.md` to
  remove the role from shadow status. From the next wave on, the orchestrator
  drops the hand-draft and uses the worker output directly. Reviewer pass is
  still required, same as any other worker.
- **Drift or failure → diagnose.** If the worker output is consistently weaker
  in one dimension, the issue is the skill prompt, the input contract, or the
  model choice — usually in that order. Iterate on the skill prompt and re-run
  shadow for another wave.

### Phase 4 — Memory update on promotion

When a role moves from shadow to active, `feedback_shadow_mode_active.md` reflects
the change with the date and the wave that validated it. Example line:

```
- reviewer: promoted 2026-05-11 morning (Epic 3 W5 close)
- scribe:   promoted 2026-05-11 evening (Epic 3 W5 close)
```

This memory is consulted at the start of every implementation task. It is the
authoritative record of which workers are default-on.

## When this lives in your CLAUDE.md

If you want the orchestrator to default to these patterns automatically, add this
snippet to your project's `CLAUDE.md`:

```markdown
## Contract sheets

- When two sub-tasks in the same scope would both inline the same upstream
  contract, sink it to `docs/contracts/<scope>.md` and reference instead.
- Sheets are verbatim from source. Code change and sheet update in the same PR.
- Reviewer rejects any PR that modifies a function appearing in a contract sheet
  without updating the sheet.

## New worker roles

- New worker roles start in shadow: hand-draft AND dispatch the worker for the
  first 1–2 waves; compare per task.
- Promote when comparisons are clean; iterate the skill prompt otherwise.
- Memory file `feedback_shadow_mode_active.md` records who is shadow vs active.
```
