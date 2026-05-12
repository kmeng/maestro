# Dispatch Protocols — Writing Specs Your Coder Can Actually Execute

Spec quality is the dominant variable in worker output quality. A precise spec produces
run-ready code in one shot; a vague spec produces plausible-looking output you have to
fix. This guide is the protocol for writing specs `coder` can act on directly.

## The default: coder is your default for any code change

Every code change goes to `coder` unless you have a specific reason it can't. This is
the economic core of Maestro — if you take work back to the orchestrator, you are paying
flagship-model prices for execution. Modifications to existing files are the majority of
real codebase work, and they are absolutely coder's job.

The mistake to avoid: deciding "this is too tricky for coder, I'll just do it myself."
The cost of that decision is invisible until you look at your token spend and realise
you have been doing the dogfooding-bypass thing repeatedly.

## Spec structure that works

A coder spec has three sections. Keep them in this order:

1. **What files this dispatch touches** — explicit list, marked "new" or "modify"
2. **For each "modify" file: the full current content** (see next section)
3. **Required behaviour / acceptance criteria** — what the new state must look like

That is enough scaffold. Add hard constraints (Python version, library versions, "do not
touch X") only when they are real constraints. Boilerplate "be precise" or "follow the
style of the project" reminders waste tokens without changing output.

## Modifying an existing file: send its current content, in full

Coder cannot see your repo. When you ask it to "add a probe call to `bootstrap/server.py`
after `load_credentials(...)`", it has no way to know what the rest of that file looks
like. If you do not include the current content, coder will infer — and inferred output
usually rewrites the file with a plausible stub that overwrites real code.

Send the file's full current content inside the spec, clearly marked as "current
content — read-only reference":

```
## File to modify: bootstrap/server.py

### Current full content (read-only reference)

```python
<paste full file here>
```

### Required edits

1. After the `load_credentials(...)` call (around line 61), insert: ...
2. Replace `model=MODEL_PRO,` in `_coder_impl` with `model=model,`.
```

Then coder produces the full new file. You diff it against the original to verify the
surgery touched only what you asked, and write the result to disk.

**Yes, this means your specs are longer.** The alternative is silent overwrites of code
you wanted to keep, plus a fix cycle after.

Reserve "I'll modify this file myself" only for genuine edge cases:

- A file larger than coder's context window where the edit is one trivial line
- A file containing secrets that should not appear in a worker dispatch
- A `pyproject.toml` / `Cargo.toml` style dependency bump — one line, no creative work

For everything else: send the file, dispatch coder.

## New files: just describe the contract

For new files, the spec is the contract. Be specific about:

- The file's path (relative to the repo root)
- The public API: exact names, signatures, types
- Behaviour cases enumerated as the test list (see test enumeration below)
- Anything that won't be obvious from the API (a non-obvious algorithm, a tricky edge
  case, a domain rule)

Skip stylistic prescriptions. Coder follows reasonable conventions on its own. Saying
"use Python 3.10+ syntax" is fine; saying "use 4-space indents and snake_case names" is
filler.

## Enumerate tests up front

The cleanest specs list every test case the implementation must pass, with one line per
test. This serves two purposes:

1. It pins down the acceptance criteria more precisely than prose can.
2. If you adopt the test-first protocol (see `tdd-with-workers.md`), this enumeration is
   what you dispatch first.

A test list looks like:

```
### Required tests

1. `test_role_id_accepts_canonical_four` — happy path, all 4 roles, assert keys match.
2. `test_role_id_rejects_unknown_role` — extra "architect" role → ValidationError.
3. `test_member_empty_after_strip_rejected` — `"   "` → ValidationError with "empty" in message.
...
```

The test names are the documentation. If a test name takes more than one short clause to
explain, the test is doing too much — split it.

## When the worker's `concerns` section says it inferred something

Worker output ends with a `concerns` section. If concerns mention "inferred", "assumed",
"plausible default", or "typical project structure" on a file the spec was supposed to
fully specify, that file's output is suspect. Read it with skepticism, diff aggressively
against your original, and treat any change outside your stated requirements as a finding
to reject or accept deliberately.

Don't dismiss the concerns. They are the worker telling you it had to guess. Better to
catch a wrong guess at integration time than to merge it.

## What "small enough" looks like

A useful dispatch is one focused thing. Signs you are dispatching too much at once:

- More than ~5 files in a single dispatch
- A mix of unrelated changes (a feature + a refactor + a test cleanup)
- Spec text running past ~500 lines

When you notice this, split. Two focused dispatches almost always produce cleaner output
than one giant one, and each dispatch is faster.

## What this looks like in your CLAUDE.md

If you want your orchestrator to apply these defaults automatically, add this snippet to
your project's `CLAUDE.md`:

```markdown
## When dispatching to Maestro's coder

- Every code change is coder's job, including modifications. Don't take work back to
  yourself except for genuine edge cases.
- For modifications: include the file's full current content in the spec as a read-only
  reference, then enumerate the exact edits.
- New files: specify path, public API, and the test list. Skip stylistic prescriptions.
- If coder's `concerns` section mentions "inferred" or "assumed", diff the output against
  the original carefully — that's the worker flagging a guess.
- Keep dispatches focused: ~5 files max, one coherent change.
```
