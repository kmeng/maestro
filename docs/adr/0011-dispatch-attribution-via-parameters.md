# ADR-0011: Dispatch attribution via parameters (with branch fallback)

**Status**: accepted
**Date**: 2026-05-10
**Issue**: #64
**Supersedes**: D7 in #56 (env-var attribution helper)

## Context

Epic 6's first attribution model (D7 in #56, design 56 §3.2) read
`MAESTRO_CURRENT_TASK` / `MAESTRO_CURRENT_ISSUE` from environment
variables, set by `source scripts/begin_task.sh <task> <issue>` before
launching Claude Code. The MCP server is a separate process; it
inherits env at startup, so `source` only takes effect for the
*next* Claude Code session. In practice this meant: forget to source
→ every dispatch unattributed, silently.

Two failures of this design surfaced 2026-05-10:

1. **Friction**. For shipped users — who install maestro and use it
   for whatever they're working on — sourcing a shell script before
   launching their editor is unacceptable. Different users have
   different task systems (GitHub Issues, Linear, Jira, none); the
   helper assumes one of them.

2. **Conflation**. The env-var design assumed task attribution must
   come from *outside* the MCP server because the server doesn't
   know what task it's running. But the *orchestrator* (Claude Code)
   does know — it just opened the issue per implementation-start
   protocol. The right move is to push the knowledge into the dispatch
   call, not externalise it via env.

## Decision

Adopt **parameter-based attribution with git-branch fallback**.

### Attribution sources (precedence)

1. **Explicit parameter** on each worker tool call. Workers
   (`coder`, `librarian`, `reviewer`, `scribe`) accept optional
   `task_id` (string) and `issue_number` (int). For `scribe`, the
   existing required `issue_number` (used for commit-message
   formatting) is reused — no separate attribution param.
2. **Env var (deprecated)**. `MAESTRO_CURRENT_TASK` /
   `MAESTRO_CURRENT_ISSUE` continue to work as a backward-compatible
   fallback. First use per process emits `DeprecationWarning`.
   Removed in v0.0.4.
3. **Git branch inference**. Server parses
   `(feature|fix|refactor|docs)/<n>-<slug>` from the current branch.
   Only `issue_number` is inferable — branch names don't reliably
   carry task IDs.
4. **Unattributed**. Both stay `None`. Row recorded with `noattr` in
   `row_id`; surfaced in renderer's "unattributed" footnote.

Explicit param is partial-friendly: passing only `task_id` or only
`issue_number` does *not* backfill the other from env / branch. This
prevents stale env values from leaking into intentional partial
attributions.

### Worker schema changes

Optional `task_id` and `issue_number` properties added to coder /
librarian / reviewer input schemas. Scribe gains only optional
`task_id`; its existing required `issue_number` field doubles as
attribution.

### Branch inference helper

`_infer_issue_from_branch()` runs `git rev-parse --abbrev-ref HEAD`
under the maestro_server cwd, with 2s timeout, and applies regex
`^(feature|fix|refactor|docs)/(\d+)-`. Fail-soft: any error
(non-zero exit, no git, regex miss, int parse error) returns `None`.
Recomputed per emit — branch can change mid-session.

### Deprecation timeline

- **v0.0.3 (this ADR)**: parameter path added; env-var path read but
  warns; `begin_task.sh` echoes deprecation to stderr.
- **v0.0.4**: env-var read removed from `_emit_dispatch_row`;
  `begin_task.sh` deleted from repo.

## Alternatives considered

- **Project-local config file** (`.maestro/current_task`).
  Rejected: still requires user setup per task, just shifts the
  friction from shell to file. Branch inference covers the
  "I started a feature/N-foo branch" case more naturally with zero
  setup.

- **Read task from a CLAUDE.md or .claude/state file written by the
  orchestrator at session start**. Rejected: introduces orchestrator
  ↔ server file coupling that's invisible to other MCP clients;
  parameter-passing is explicit, transport-agnostic, and documented
  on the tool surface itself.

- **Make `task_id` / `issue_number` required on all four tools**.
  Rejected: breaks general-user case (no GitHub-issue concept) and
  blocks ad-hoc dispatches. Optional + branch fallback + unattributed
  bucket covers the spectrum.

- **Embed attribution in a header-style channel like
  `arguments["_meta"]["task_id"]`**. Rejected: adds a parallel
  metadata namespace for one feature; first-class params are
  cleaner and self-documenting in the schema.

- **Separate `attribution_issue_number` field on scribe to avoid
  reusing the required `issue_number`**. Rejected: same number
  semantically (the issue this dispatch contributes to). Two fields
  would invite drift between them. Reuse keeps scribe's contract
  clean. (Note: scribe's required `issue_number` itself is workflow-
  coupled — separate concern, tracked in
  `project_pure_worker_schemas.md`.)

## Consequences

### Good

- Zero user setup for the common case. Orchestrator passes the
  values it already knows; ad-hoc users get branch-fallback for free.
- Explicit at the tool-call site — no hidden global state.
- Backward-compatible: existing env-var users see only a one-time
  warning per process, not a hard break.
- Pattern generalises: any new worker tool added later just needs the
  same two optional params + plumbing into `_emit_dispatch_row`.

### Bad / risks

- **Two API surfaces during the deprecation window** (params + env).
  Users following old docs may continue to use env. The deprecation
  warning + design-doc update are the only signals; users who suppress
  warnings won't see them.
- **Git subprocess on every emit**. Adds ~10-30ms per dispatch on
  Mac/Linux. Acceptable: dispatches are 60-500s; emit overhead is
  noise.
- **Branch convention assumes the project's branch naming** (the four
  prefixes). For users with different conventions, branch inference
  silently misses; they fall to unattributed. Documented in
  methodology page (T6.4) under "How attribution works".

### Reversibility

**High.** The parameter shape is additive (new optional fields).
Reverting would mean removing the params, removing the branch helper,
restoring env-var as the only source — all mechanical. The hardest
part to revert is users having adopted parameter-passing in their
orchestrator prompts; but that's a "lose a small UX improvement",
not a data-loss risk.

## Sibling open questions resolved

- D7 in #56 (env-var via begin_task.sh) — superseded by this ADR.

## Open questions deferred

- Worker schema purity (scribe's required `issue_number / title /
  body` is workflow-coupled even after this ADR). Tracked in
  `project_pure_worker_schemas.md`; likely Epic 7 scope.
