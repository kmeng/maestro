# ADR-0008: Worker role naming and I/O contract conventions

**Status**: accepted
**Date**: 2026-05-09
**Issue**: #52

## Context

v0.0.2 shipped a single worker role, `cheap_code_gen`. v0.0.3's first
implementation task surfaced a need for several more roles
(`librarian`, `reviewer`, `scribe`). Before adding them piecemeal, the
project needs durable conventions for:

- **Naming** — what a role is called, and what shape that name takes.
- **I/O contract** — how role inputs and outputs are structured so the
  orchestrator and the role can interoperate without one-off adapters.
- **Rollout** — how a new role is introduced when its quality is not
  yet trusted in production.

Without these conventions, every new role becomes a small bespoke
design exercise. The fleet is going to grow (Epic 1's vision section
already names "additional reviewer/refactorer roles" as candidates);
codifying the conventions now keeps the cost of each new role low.

## Decision

### Naming convention

Role names are **team-member-style nouns**, in lowercase, single token
where possible:

- `coder` (formerly `cheap_code_gen`)
- `librarian` — long-document reading and extraction
- `reviewer` — code review against spec
- `scribe` — commit message and PR body drafting

Rules:

1. **Noun, not verb-object.** `librarian`, not `read_doc`. The fleet
   reads as a team roster.
2. **No `cheap_` prefix.** The `mcp__maestro__` MCP tool prefix already
   identifies these as Maestro workers; `cheap_` is redundant and reads
   as derogatory.
3. **Single token preferred.** Multi-token names (e.g.,
   `frontend_engineer`) are allowed when one word is genuinely
   ambiguous, joined by underscore.
4. **No model in the name.** `coder`, not `deepseek_coder`. Model
   assignment is configurable per Epic 1 (`team.yaml` schema); the
   role name describes the job, not the worker.
5. **Plural roles get suffixes when needed.** Two coders on a project
   become `coder_a` / `coder_b` or named members per Epic 1's named-
   member layer. The role itself stays `coder`.

### I/O contract pattern

Every role follows this contract shape:

**Input**: a structured record matching a Pydantic-style schema
declared in the tool's MCP `inputSchema`. Required fields are
required; optional fields have explicit defaults. The schema is the
source of truth — undocumented inputs are not honored.

**Output**: a structured response that always includes:

- The role's primary deliverable (`hard_constraints`, `verdict`,
  `commit_message`, etc.) — name varies by role.
- A `concerns` field — list of strings — for the worker to surface
  ambiguities, self-doubt, or contradictions. This is the worker's
  channel to flag that the spec was unclear or the input was
  inadequate, without inventing a confident answer.

The handler validates output structure before returning to the
orchestrator. Schema mismatches return a structured error, not
malformed JSON.

**Verbatim contract** for fields that promise verbatim quotes (e.g.,
`librarian.hard_constraints[*].quote`) — paraphrasing in those fields
is a contract violation and is grounds for the orchestrator to reject
the response and refine the role's system prompt.

**Verbatim verification** (added 2026-05-09 after T5.1 real-world
testing). The system prompt alone does not enforce verbatim contracts:
v4-flash was observed to strip markdown emphasis (`**X**` → `X`) and
silently paraphrase quotes despite explicit prompt rules. Any role
declaring a verbatim contract on a field MUST have its handler verify
quotes against the source before returning. Convention:

- Verification compares quote-vs-source after normalizing whitespace
  (line wraps and indentation collapse to single spaces). This avoids
  false rejection when the worker re-flows paragraph content. All
  other characters — markdown emphasis, punctuation, exact wording —
  must match.
- Non-verbatim entries are **dropped** from the field — they never
  reach the caller.
- The handler appends a summary note plus per-entry violation lines
  to the response's `concerns` field so the caller can see what was
  dropped.

The verifier is the contract enforcer; the system prompt is the
expectation-setter. Both are needed, neither is sufficient alone.

### Worker file access (token-economy principle)

Workers MAY read files from the local filesystem when the input the
caller would otherwise have to pass is large enough that loading it
into the orchestrator's context defeats the purpose of dispatching.

The principle: if dispatching the task to a cheap worker forces the
orchestrator to first load the input into its (expensive) context, the
dispatch is hollow — the orchestrator pays the input cost regardless.
Letting the worker read the file directly keeps the data in the cheap
worker's context only; the orchestrator sees only the small structured
output.

**Convention**: roles whose primary input is a file (currently:
`librarian`) accept a `file_path` field in their input schema. The
worker handler reads the file, passes its content as part of the model
prompt, and returns only the structured extraction. An optional
`document_text` field provides an escape hatch for content not on disk
(e.g., remote API responses) — exactly one of `file_path` /
`document_text` must be set.

This convention does not apply to roles whose input is genuinely small
(e.g., `scribe` takes a diff and an issue body that the orchestrator
already has in context for the same task it is committing).

### Shadow-mode rollout

A new role launches in **shadow mode** when its quality is not yet
proven. Mechanics:

- Memory file `feedback_shadow_mode_active.md` lists the roles
  currently in shadow. Membership is the single source of truth for
  whether a role is in shadow or default.
- For tasks involving a shadow-mode role, the orchestrator does its
  own version of the work AND dispatches to the worker, presenting
  both versions to the user side-by-side.
- **Promotion** is by explicit user signal. The orchestrator removes
  the role from the memory file and stops running its own parallel
  version.
- **De-promotion** if a problem surfaces post-promotion: re-add the
  role to the memory file.

Shadow mode is a workflow contract, not a code mode. The worker code
is identical whether the role is in shadow or default; only the
orchestrator's surrounding protocol differs.

### When to write a new role

Triggers for adding a role:

- A pattern of orchestrator work is observed to be (a) frequent,
  (b) execution-heavy, and (c) judgment-light enough for a cheap
  worker.
- The pattern has a clear input/output shape stable across instances.

If a candidate doesn't meet all three, it stays with the orchestrator.

## Alternatives considered

- **Verb-object naming (`read_doc`, `review_code`)** — rejected. Less
  evocative of the AI-software-team metaphor; harder to talk about
  ("ask the doc reader to..." vs "ask the librarian to..."). The
  metaphor is load-bearing for v0.0.3's product story.
- **Keep `cheap_` prefix; add `cheap_librarian` etc.** — rejected.
  Doubles down on a prefix that conveys "low-quality" and is redundant
  with the MCP namespace.
- **Flat output (no `concerns` channel)** — rejected. Without an
  explicit channel for worker self-doubt, the worker either invents a
  confident answer (worse for the orchestrator) or drops the doubt
  entirely (lost signal).
- **Promote new roles directly to default; iterate on quality
  in-flight** — rejected. The orchestrator has no way to know whether
  a worker's output is correct without doing the work itself for a
  while; without shadow mode that comparison never happens
  systematically.
- **Make shadow-mode a code-level toggle in the worker** — rejected.
  The behavior difference lives in the orchestrator's protocol, not
  in the worker. A code toggle in the worker would be machinery
  without payoff.

## Consequences

### Good

- New roles cost less to introduce. Each one is a system-prompt + I/O
  schema + tool registration; no per-role design exercise about
  "what shape should this take."
- The fleet reads as a coherent team. User-facing artefacts (Epic 1's
  team UI, dispatch log) stay readable as the fleet grows.
- The `concerns` channel gives the orchestrator a structured signal
  for "this dispatch was risky," which is hard to extract from
  free-form text.
- Shadow mode lets the project add experimental roles without
  betting the workflow on unproven quality.

### Bad / risks

- **Naming-as-marketing risk.** `librarian` is cute but the metaphor
  could break if the role's actual responsibility drifts. Mitigation:
  ADR-revising is cheap; rename if it stops fitting.
- **`concerns` channel can be ignored.** A worker that always returns
  `concerns: []` provides no value over one without the channel.
  Mitigation: orchestrator's own observation; system prompts
  explicitly invite the worker to use the channel.
- **Shadow-mode protocol is informal.** No timer, no metric. If
  evaluation drags on, roles linger in shadow and the orchestrator
  carries the parallel cost. Mitigation: lightweight, deliberate —
  the user owns promotion timing.

### Reversibility

**High.** Naming convention can be revised by a future ADR and a
batch rename — the rename PR-B in this epic is the template. I/O
contract can evolve per role; backward compatibility is moot because
every caller is internal to Maestro. Shadow-mode protocol is
documented in feedback memory and a design doc, both editable.

## Sibling open questions resolved by this ADR

- Epic 5 OPEN: how new roles should be named, structured, and rolled
  out. Resolved as above.
- Epic 1 vision-doc OPEN-V2 (1:N member-per-role) — partially
  bordering: this ADR keeps role names singular; Epic 1 owns whether
  a role can have multiple named members.
