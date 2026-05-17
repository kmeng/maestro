<!-- Epic 8 external smoke checklist — verify new tools ship clean for non-Maestro projects (T8.7 AC4) -->

# Epic 8 external smoke — non-Maestro project validation

> Verify the three new tools shipped in Epic 8 (`librarian` with `file_paths`,
> `verifier`, `spec_writer`) and the redesigned `scribe` schema work in a
> fresh Claude Code session attached to a project that has **no Maestro
> concepts** (no `team.yaml`, no Maestro epic/issue workflow).

## 0. Pre-requisites

- [ ] Maestro installed in a venv (`pip install -e .` from this repo or wheel install)
- [ ] `.env` has `DEEPSEEK_API_KEY` set
- [ ] A throwaway project directory unrelated to Maestro (e.g., a Vue or Rails repo)
- [ ] Claude Code launched in that directory with `mcp__maestro` registered

## 1. Tool catalog visibility (AC4 — generic schemas)

In the test project's Claude Code, run `/mcp` and confirm the following tool
names appear under the `maestro` server:

- [ ] `mcp__maestro__coder`
- [ ] `mcp__maestro__librarian`
- [ ] `mcp__maestro__reviewer`
- [ ] `mcp__maestro__scribe`
- [ ] `mcp__maestro__verifier`     **(Epic 8 new)**
- [ ] `mcp__maestro__spec_writer`  **(Epic 8 new)**
- [ ] `mcp__maestro__job_status`

For each tool, inspect its description / inputSchema in `/mcp` output and assert
**no Maestro-workflow terminology leaks**: descriptions must not reference
"team.yaml", "Epic N", a specific issue tracker, "Maestro project", etc.
Generic terms like "task", "spec", "issue number for telemetry attribution"
are fine.

- [ ] coder: generic
- [ ] librarian: generic; mentions `file_paths` as multi-file optional input
- [ ] reviewer: generic
- [ ] scribe: generic — required fields are **only** `diff` and `purpose`
- [ ] verifier: generic
- [ ] spec_writer: generic

## 2. librarian + file_paths multi-file (T8.1)

In the test project, ask Claude Code to:

> Use librarian to read `README.md` and one other top-level file (e.g.
> `package.json`, `Gemfile`, `pyproject.toml`) in a single call via `file_paths`.
> Surface what the project is about.

- [ ] librarian dispatches successfully
- [ ] Returns one consolidated extraction citing both files
- [ ] Banner shows `librarian` + the chosen model

## 3. verifier (T8.2)

Ask Claude Code to:

> Use verifier to check 3 claims about the project's `package.json` (or
> equivalent): one true, one false, one ambiguous.

- [ ] verifier dispatches successfully
- [ ] Returns `verifications: [...]` with 3 entries, statuses spanning
      `verified` / `incorrect` / `ambiguous`
- [ ] `evidence` field references the source

## 4. spec_writer (T8.3)

Ask Claude Code to:

> Use spec_writer to draft a coder spec for a tiny task in this project
> (e.g., "add a function `greet(name)` to `utils.js`"). Provide 2 acceptance
> criteria and 1 line of upstream context.

- [ ] spec_writer dispatches successfully
- [ ] Returns `{spec, verification_checklist, concerns}` shape
- [ ] `verification_checklist` has ≥ 1 entry per `output_files` entry
- [ ] `spec` text is ready-to-dispatch (could be pasted into coder directly)
- [ ] No Maestro-specific section references in the spec text

## 5. scribe — new schema (T8.8)

Ask Claude Code to:

> Use scribe to draft a commit message for a hypothetical diff
> ("fix: handle missing config gracefully"). Provide a free-form purpose;
> do NOT provide any GitHub issue context.

- [ ] scribe accepts call with only `diff` + `purpose`
- [ ] Does NOT require `issue_number` / `issue_title` / `issue_body`
- [ ] Returns `commit_message` (non-empty) + `pr_title` / `pr_body` (may be empty
      for `style="commit message"`)

## 6. Negative tests — workflow leak check

For each new tool, attempt a call with intentionally Maestro-flavored
arguments to confirm they are NOT required:

- [ ] `verifier`: call without `task_id` / `issue_number` → succeeds
- [ ] `spec_writer`: call without `task_id` / `issue_number` → succeeds
- [ ] `scribe`: call without `issue_number` → succeeds (telemetry row carries `null`)

## 7. Sign-off

- [ ] All checkboxes above checked
- [ ] No leak of Maestro workflow concepts in shipped tool surfaces
- [ ] Notes any surprises in `docs/journal/<date>-epic8-external-smoke.md`

If any check fails, file an issue tagged `epic-8-followup` and reference
this checklist line.
