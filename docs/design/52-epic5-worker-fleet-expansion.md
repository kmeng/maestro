# Design: Epic 5 — worker fleet expansion

**Issue**: #52
**Status**: approved

> Approved 2026-05-09 after pass-1 with two corrections folded in:
> (1) model assignments use the actual DeepSeek v4 lineup
> (`deepseek-v4-flash` / `deepseek-v4-pro`); (2) `librarian` worker
> reads files directly via `file_path` to keep document text out of the
> orchestrator's context — this is the load-bearing token-economy
> reason this role exists. ADR-0008 records the worker-file-access
> convention.

## Problem

v0.0.3's first implementation task (T0.1, #19) surfaced a real cost
pattern. The orchestrator (Claude Opus) spent significant tokens on
execution-heavy work that did not require orchestrator-level reasoning:

- Reading whole 14 KB design docs to extract a few hard constraints
  relevant to the task at hand.
- Reviewing worker-generated code line-by-line against the spec.
- Drafting commit messages and merge messages from a known diff and
  issue body.

The current worker fleet has exactly one role — `cheap_code_gen` (a
DeepSeek-Coder caller) — which does not cover any of these patterns.
Three new roles round the fleet out so that more of the work the
orchestrator routinely does becomes dispatchable to cheaper models.

A naming cleanup lands alongside: rename `cheap_code_gen` → `coder` for
consistency with the team-member-style names introduced here. The
`cheap_` prefix is redundant (the `mcp__maestro__` namespace already
identifies these as Maestro workers) and reads as derogatory.

This epic is itself a dogfooding artefact. The cost pattern was observed
during dogfooding (T0.1's full implementation flow). The remedy is more
dogfooding capacity. The economics expected: the librarian role pays for
itself across the remaining 32 v0.0.3 implementation tasks, all of
which start by reading design docs the orchestrator does not need to
ingest in full.

## Out of scope

- Standing role-catalog UI. Epic 1 T1.5 owns the visualization of which
  roles exist and which models serve them.
- `team.yaml` configuration of role→model bindings. Epic 1 owns user
  configurability; Epic 5 fixes sensible defaults that Epic 1 can
  override.
- Role-discovery / dynamic role loading. All roles in v0.0.3 are
  hardcoded in `bootstrap/maestro_server.py`.
- Replacing the orchestrator's role in plan-stating, architecture
  decisions, or end-user dialogue. Those remain orchestrator-only.
- Auto-promoting a shadow-mode role based on a numeric quality
  threshold. Promotion is an explicit user decision.

## Functional design

After this epic lands, the orchestrator's workflow gains three new
dispatch points:

**At the start of an implementation task** — instead of reading a whole
design doc and ADR, the orchestrator dispatches to `librarian` with the
document text plus a query lens ("extract everything relevant to T0.X").
The librarian returns hard constraints as verbatim quotes, paraphrased
summary of relevant sections, and pointers to sections it could not
confidently summarize. Orchestrator may still spot-read those sections.

**After worker code arrives** (currently only from `coder`) — the
orchestrator dispatches to `reviewer` with the spec and the worker's
code. The reviewer returns a verdict (pass / concerns / fail) plus a
findings list. In shadow mode, the orchestrator also performs its own
review and presents both versions to the user.

**Before committing a change** — the orchestrator dispatches to `scribe`
with the diff, the issue body, and the project's commit-message
conventions. The scribe returns a commit message and PR body draft. In
shadow mode, the orchestrator drafts its own and presents both.

For shadow-mode roles, the user evaluates side-by-side and either picks
one, edits, or asks for a re-draft. After enough evaluations, the user
explicitly promotes the role out of shadow mode; from then on the
worker's output is the default and the orchestrator skips the parallel
draft step.

## Technical design

### Role catalog and naming convention

This epic establishes the convention recorded in
[ADR-0008](../adr/0008-worker-role-naming-and-io-conventions.md):

- Role names are **team-member nouns**: `librarian`, `reviewer`,
  `scribe`, `coder`. Not `cheap_*`, not verb-object form.
- Each role has a structured I/O contract — a Pydantic-style input
  schema, a structured output that always includes a `concerns`
  channel for the worker to flag spec ambiguities or self-doubt.
- New roles may launch in **shadow mode** before being promoted to
  default. Shadow mode is a workflow contract, not a code mode — the
  worker itself runs identically; only the orchestrator's surrounding
  protocol differs.

### Role: `librarian`

**Job description**: read a long document and extract the parts
relevant to a query, with hard constraints quoted verbatim.

**Tool description (MCP-visible)**:

> Extract task-relevant content from long documents (design docs, ADRs,
> journal entries, etc.). USE for: focused reading of large reference
> material to surface constraints, decisions, and relevant context. DO
> NOT USE for: documents you have already cited specific lines from;
> live operational data; reading code (use `reviewer` for code).

**Input**:

| Field | Type | Description |
|---|---|---|
| `file_path` | string (optional) | Absolute or repo-relative path to the document. Worker reads the file. **Preferred** when the document is on disk — keeps the document text out of the orchestrator's context entirely (the document only lives in the worker's context). |
| `document_text` | string (optional) | Inline document content. Used when the source is not a file (e.g., a GitHub issue body the orchestrator already received). |
| `query` | string | The lens — what the caller is looking for. E.g. "I am implementing T0.2 of Epic 0; surface the relevant constraints". |

Exactly one of `file_path` or `document_text` must be provided.

**Token economy note**: this is the load-bearing reason the librarian
exists. If the orchestrator reads the file itself and passes
`document_text`, the document hits the orchestrator's (expensive) context
in full; the worker is mostly cosmetic. Routing via `file_path` keeps the
document in the (cheap) worker context only — the orchestrator sees only
the small structured summary. Callers should pass `file_path` whenever
the document is on disk.

**Output**:

| Field | Type | Description |
|---|---|---|
| `hard_constraints` | list of `{quote: string, section: string}` | Verbatim quotes of constraints the caller must satisfy, paired with the section they came from. **Verbatim is a contract**; paraphrased text in this field is a contract violation. |
| `summary` | string | Paraphrased summary of relevant content, in the librarian's own words. |
| `recommend_full_read` | list of strings | Section names the librarian could not confidently summarize, recommending the caller read directly. |
| `concerns` | list of strings | Anything the librarian noticed that the caller might want to know — ambiguities, contradictions with other docs, etc. |

**System prompt skeleton** (note: file reading happens in the handler, not the LLM; the LLM receives the document content as part of its prompt):

> You are a librarian on an AI software team. Your job is to read long
> reference documents and extract exactly what the caller needs for the
> task they describe.
>
> Strict rules:
> - In `hard_constraints`, every quote must be VERBATIM from the source
>   document. Paraphrasing here is a contract violation. If you cannot
>   find a verbatim constraint, omit the entry rather than invent one.
> - In `summary`, paraphrase freely; this is your understanding.
> - In `recommend_full_read`, list section names where you are not
>   confident your summary captures the nuance. Better to be honest
>   than confident.
> - In `concerns`, surface anything that surprised you, contradicted
>   other docs, or seemed under-specified.

**Model**: `deepseek-v4-flash` (low-judgment extraction; promote to
`deepseek-v4-pro` later if quality issues observed).

**Failure modes**:

- Hallucinated quotes in `hard_constraints` — the highest-stakes
  failure. Mitigation: orchestrator spot-checks one or two quotes
  against the source on every call; deviations are reported and the
  role's system prompt is tightened.
- Too-aggressive summarization (loses key nuance). Mitigation: the
  `recommend_full_read` field is the librarian's own escape hatch.
- Empty output on poorly-framed query. Mitigation: orchestrator's job
  to write a focused query.
- `file_path` not found / not readable. Handler returns a structured
  error before invoking the model. Caller can retry with corrected
  path.
- File larger than the worker's context window. Handler refuses
  before invoking the model and returns a structured error in
  `concerns` with the observed file size; caller decides whether to
  pass a smaller slice (`document_text`) or split the request. v0.0.3
  does not chunk on the worker side; see OPEN-5.1.

### Role: `reviewer`

**Job description**: judge whether code matches a spec.

**Tool description (MCP-visible)**:

> Review code against a spec. USE for: pass/fail judgment on whether
> worker-generated code matches a spec; finding spec/code drift;
> flagging missed acceptance criteria. DO NOT USE for: subjective
> style review; architectural decisions; security review;
> cross-file reasoning.

**Input**:

| Field | Type | Description |
|---|---|---|
| `spec` | string | The spec the code was supposed to implement, including hard constraints. |
| `code` | string | The code under review. |
| `language` | string | Programming language. |

**Output**:

| Field | Type | Description |
|---|---|---|
| `verdict` | enum: `pass`, `concerns`, `fail` | `pass` = matches spec; `concerns` = matches but has issues worth surfacing; `fail` = doesn't match. |
| `findings` | list of `{severity: high\|medium\|low, location: string, description: string}` | Specific issues. `location` is a function name or line range. |
| `missed_requirements` | list of strings | Acceptance-criteria items the code did not address. |
| `concerns` | list of strings | Spec ambiguities or things the reviewer was unsure how to judge. |

**System prompt skeleton**:

> You are a code reviewer on an AI software team. Your job is to judge
> whether code matches a spec. You are NOT here to redesign, refactor,
> or improve style — only to verify correspondence to the spec.
>
> Strict rules:
> - Verdict `pass` requires every spec requirement to be addressed.
> - Verdict `fail` requires at least one high-severity finding or
>   missed requirement.
> - Cite specific function names or line ranges in `location`.
> - If the spec is ambiguous, flag in `concerns` rather than guessing.

**Model**: `deepseek-v4-pro` (judgment-heavy work; the cost premium over
flash is justified for review quality).

**Rollout**: shadow mode. Orchestrator continues to do its own review
for every dispatch; both versions shown to user. Promotion criterion is
explicit user signal.

**Failure modes**:

- Verdict `pass` on code that fails (false positive). Mitigation:
  orchestrator's parallel review during shadow period catches it.
- Over-eager `fail` on stylistic preferences (false negative on a
  passing implementation). Mitigation: system prompt explicitly forbids
  style review.

### Role: `scribe`

**Job description**: draft commit messages and PR bodies from a diff
and issue context.

**Tool description (MCP-visible)**:

> Draft commit messages and PR bodies. USE for: Conventional Commits
> message + PR body from a git diff plus issue context. DO NOT USE
> for: release notes (different scope); code comments; user-facing
> documentation.

**Input**:

| Field | Type | Description |
|---|---|---|
| `diff` | string | `git diff` output of the change. |
| `issue_number` | int | Issue this commit addresses. |
| `issue_title` | string | Issue title for context. |
| `issue_body` | string | Issue body for context. |
| `convention` | string | Project's commit conventions, including Conventional Commits prefix rules, co-author attribution, and `Closes #N` placement rules. |

**Output**:

| Field | Type | Description |
|---|---|---|
| `commit_message` | string | Full commit message subject + body, including co-author lines. |
| `pr_title` | string | Suggested PR title (under 70 chars per Maestro convention). |
| `pr_body` | string | PR body in Markdown, following project format. |
| `concerns` | list of strings | Things the scribe was unsure about (e.g., whether to use `feat:` or `refactor:`). |

**System prompt skeleton**:

> You are a scribe on an AI software team. Your job is to write
> commit messages and PR bodies that follow the project's conventions
> exactly.
>
> Strict rules:
> - Subject line under 80 chars; Conventional Commits prefix.
> - Body explains the WHY (motivation, decision), not the WHAT (the
>   diff itself shows the WHAT).
> - Include `Closes #N.` on its own line if the convention says so.
> - Include co-author lines per the convention.
> - Do not invent details not present in the diff or issue.

**Model**: `deepseek-v4-flash` (routine drafting from structured input).

**Rollout**: shadow mode.

**Failure modes**:

- Inventing details not in the diff — biggest risk. Mitigation: explicit
  system-prompt rule + orchestrator review during shadow.
- Wrong Conventional Commits prefix (e.g., `feat:` for a refactor).
  Mitigation: orchestrator review.

### Shadow-mode protocol

**Activation**: a role is in shadow mode when listed in the
`feedback_shadow_mode_active.md` memory file. Adding the role to that
list activates shadow; removing it promotes the role to default.

**Per-task workflow when a role is in shadow mode**:

1. Orchestrator does its own version of the work (review / commit
   message / etc.) using its normal flow.
2. Orchestrator dispatches the same input to the shadow-mode worker.
3. Orchestrator presents **both versions side-by-side** to the user
   in the conversation, labeled clearly (e.g., "**Orchestrator
   draft**" vs "**Reviewer worker draft**").
4. User picks one, edits, or asks for re-draft. The decision is acted
   on; the data point is informally noted.

**Promotion**: explicit user signal — "promote reviewer out of shadow"
or equivalent. The orchestrator updates the memory file, and on the
next task does not run its own parallel version (only dispatches).

**De-promotion**: if the user signals a problem after promotion, the
role goes back to shadow mode by re-adding it to the memory list.

**Memory file format** (`feedback_shadow_mode_active.md`):

```markdown
---
name: Shadow-mode roles (active evaluation period)
description: Roles currently in shadow-mode rollout — orchestrator runs its own version in parallel and presents both to user
type: feedback
---

Roles in shadow mode (orchestrator runs in parallel, both versions shown to user):

- `reviewer` — added 2026-05-09. Promotion criterion: explicit user signal.
- `scribe` — added 2026-05-09. Promotion criterion: explicit user signal.
```

When the list is empty, no role is in shadow mode and the orchestrator
dispatches all eligible work directly.

### Renaming `cheap_code_gen` → `coder`

13 files reference `cheap_code_gen` as of design time. All textual
references update per the rule below. The rename lands in PR-B
alongside librarian implementation, since that PR is the natural moment
a reader will see the new naming convention land.

**Model bump (added during T5.1 kickoff)**: PR-B also bumps `coder`'s
underlying model from `deepseek-coder` to `deepseek-v4-pro` per the
resolution of OPEN-5.6. The rename is therefore not strictly textual
— callers will observe a different model on the other end of the
tool. Behavior shape is unchanged (same I/O contract); only the
serving model changes.

Files affected (per `grep -rn cheap_code_gen`):

- `bootstrap/maestro_server.py` — function and tool definition
- `bootstrap/QUICKSTART.md` — usage examples
- `BUILD_LOG.md` — historical references (rewrite carefully — past
  releases really were named `cheap_code_gen`; only forward-looking
  references should change)
- `docs/journal/README.md`, `docs/journal/2026-05-08.md` — historical
  references; same caution
- `docs/design/11-product-vision.md` — vision-level mentions
- `docs/design/12-epic0-web-ui-skeleton.md` — Epic 0 mentions
- `docs/design/13-epic1-team-composition.md` — Epic 1 mentions
- `docs/design/14-epic2-project-scaffolding.md` — Epic 2 mentions
- `docs/design/15-epic3-observability.md` — Epic 3 mentions
- `docs/design/6-env-loading.md` — historical
- `docs/adr/0004-team-config-format-and-schema.md` — example mentions
- `docs/adr/0007-dispatch-log-format-and-schema.md` — example mentions

Rule for journal/BUILD_LOG: a historical fact ("v0.0.2 shipped
`cheap_code_gen`") stays as-is; a forward-looking reference ("we will
extend `cheap_code_gen`") becomes `coder`. PR-B carries this judgment
file-by-file.

## Affected modules

- **Modified**: `bootstrap/maestro_server.py` — gains four MCP tool
  definitions (`librarian`, `reviewer`, `scribe`, plus renamed `coder`
  in place of `cheap_code_gen`) and four handler implementations.
  The file grows; no further structural change in v0.0.3 (split waits
  for Epic 4 packaging).
- **Modified**: `bootstrap/QUICKSTART.md` — example commands updated to
  reference `coder`.
- **New tests**: `tests/test_workers.py` — minimal coverage that each
  tool is registered and its input schema validates expected fields.
  Mock the OpenAI client; do not make real API calls in tests.
- **Modified**: 11 documentation files for the rename (textual only).
- **New memory file**: `feedback_shadow_mode_active.md` (orchestrator
  workflow, not project artefact).

## Failure modes (cross-cutting)

- **API key missing** for new roles — already handled by the existing
  `.env` loader in v0.0.2; new roles use the same key.
- **DeepSeek rate limit** when multiple roles fire in close succession.
  Acceptable in v0.0.3 — surfaces as a tool-call error with the API's
  message; orchestrator retries or falls back to its own version.
- **Worker hallucinates structured output** that doesn't match the
  declared schema. Mitigation: the handler validates output before
  returning; on schema mismatch, returns a structured error rather than
  malformed JSON to the orchestrator.
- **Shadow-mode memory drift** — file says role is in shadow but
  orchestrator forgets to run parallel version. Mitigation: at session
  start the orchestrator reads `feedback_shadow_mode_active.md` and
  treats it as a hard checklist.

## Task breakdown

PRs in path-2 compressed flow. Each PR keeps `v0.0.3` runnable.

- **PR-A** — design doc + ADR-0008 + sub-issue creation. No code.
  This is the current PR; it lands the design doc and ADR and creates
  the two sub-issues below.
- **PR-B** — `librarian` implementation + `cheap_code_gen → coder`
  rename across the 13 files. Tracked as **T5.1 (#53)**. Includes
  registration of the new tool in the bootstrap server, system prompt
  as an inline string (per ADR-0008), output-schema validator, unit
  test (mocked client), and the rename. No shadow-mode wiring needed
  (librarian is direct rollout). (~2h)
- **PR-C** — `reviewer` + `scribe` implementations + shadow-mode
  memory feedback file. Tracked as **T5.2 (#54)**. Each role:
  registration, system prompt, output-schema validator, unit test.
  Plus the `feedback_shadow_mode_active.md` memory file populated
  with both roles. (~2.5h)

## Acceptance criteria

- [ ] `mcp__maestro__librarian` callable; output `hard_constraints`
  contains verbatim quotes (verified by orchestrator spot-check on
  first usage).
- [ ] `mcp__maestro__reviewer` callable; emits structured verdict +
  findings; runs in shadow mode per protocol.
- [ ] `mcp__maestro__scribe` callable; emits commit message + PR body;
  runs in shadow mode per protocol.
- [ ] `mcp__maestro__coder` callable with behavior identical to
  `cheap_code_gen` pre-rename.
- [ ] No file in the repo references `cheap_code_gen` as a current
  tool name (historical mentions in journals / BUILD_LOG preserved as
  historical facts).
- [ ] `feedback_shadow_mode_active.md` exists and lists `reviewer` and
  `scribe`.
- [ ] T0.1 smoke test still passes; MCP server starts cleanly.
- [ ] Each new role has at least one unit test that validates its
  input/output schema (with mocked DeepSeek client).

## Open questions

- **OPEN-5.1**: librarian on documents larger than the worker model's
  context window. v0.0.3 does not chunk on the worker side; the handler
  refuses oversized files and returns a structured error so the caller
  can decide (pass a smaller slice via `document_text`, split the
  request, or escalate). Trigger to revisit: first observed refusal in
  practice.
- **OPEN-5.2**: should `reviewer` see the worker's reasoning section
  (the `<reasoning>` block coder workers emit), or only the code? v0.0.3
  passes only the code, on the theory that reasoning could bias the
  review. Revisit if review quality lags expectations.
- **OPEN-5.3**: what counts as "enough evaluations" before promotion
  out of shadow mode is left informal. Could become a numeric
  threshold later but adds machinery v0.0.3 doesn't need.
- **OPEN-5.4**: rate-limit handling. v0.0.3 returns the API's error
  to the orchestrator and lets it decide. Revisit if it becomes a
  recurring annoyance.
- **OPEN-5.5**: cost telemetry per role (token spend, calls/day). Epic
  3's dispatch log will eventually carry this; not duplicated here.
- **OPEN-5.7**: librarian's quote hit rate. T5.1 verification observed
  `deepseek-v4-flash` producing ~40% verbatim hit rate on prose
  passages with markdown emphasis (60% dropped by the verifier). The
  role is functional — bad quotes never reach the orchestrator — but
  output volume is reduced. Trigger to revisit: usage data shows
  librarian routinely producing too few hard_constraints to be useful.
  Remediation paths: further prompt tightening, switch to
  `deepseek-v4-pro`, or adjust the verifier's normalization rules.
- ~~**OPEN-5.6**: should the renamed `coder` continue using
  `deepseek-coder` or switch to `deepseek-v4-pro`?~~ **Resolved
  2026-05-09 during T5.1 kickoff**: `coder` switches to
  `deepseek-v4-pro`. Rationale: the v4 lineup is the project's
  forward direction; keeping `coder` on the legacy `deepseek-coder`
  model would force every future prompt-tuning decision to track two
  model lineages. T5.1 carries the model bump alongside the rename;
  the original "no behavior change" framing in §3.6 is therefore
  superseded — see updated note in that section.
