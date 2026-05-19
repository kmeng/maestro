# ADR-0013: Worker roster policy for 1.0

**Status**: accepted
**Date**: 2026-05-19
**Issue**: #114
**Related**: ADR-0008 (worker role naming and I/O conventions), #72 (worker schema workflow-agnostic refactor)

## Context

Approaching v1.0, three roster-shape questions surfaced together during
scoping:

1. **Writer-style role gap** (memory: `project_writer_worker_gap`).
   Methodology articles, ADRs, design docs, journal entries, BUILD_LOG
   sections — currently all authored by the orchestrator (Claude Opus
   main session). This is the only large content-generation surface
   the worker fleet does not cover, and it contradicts the symmetric
   principle "ALL code writing goes to coder — no carve-outs"
   (memory: `feedback_coder_file_modification`).
2. **`spec_writer` promotion**. Shadow-mode role since Epic 8 close.
   Promotion would let cheaper models construct coder specs — the
   highest-output orchestrator stage today (~$0.30 per task in Opus
   output cost).
3. **Cost lever for 1.0**. Maestro's value proposition is near-flagship
   quality at 10–20% cost. Where the next real reduction comes from
   must be decided before 1.0 ships.

The decision-density principle anchored the analysis: judgment-dense
work stays at the highest capability tier; execution-dense work can be
delegated to cheaper models. The user explicitly drew this line during
the 1.0 scoping discussion: "架构设计和产品设计是良好软件系统的基础，
是成功的关键，不能把核心角色委派给能力不足的人."

## Decision

### D1. No new "writer" role. Extend `scribe` `content_type` instead.

Stripping judgment-dense content out of writer scope (ADR / design /
methodology / README / user-manual "what to say" → orchestrator + user)
leaves a small residual surface: journal entries, BUILD_LOG sections,
troubleshooting entries, user-manual "how to do it" sections.

These are all "render already-decided events/facts as structured
markdown" — the same shape `scribe` already handles for commit/PR
bodies. Adding a sibling role for the same shape would be role
inflation without architectural benefit.

Implementation: when #72 reworks `scribe`'s schema to be
workflow-agnostic, add `content_type` as a first-class dimension
covering at minimum:

- `commit_message`
- `pr_body`
- `journal_entry`
- `build_log_section`
- `troubleshooting_entry`

New content types extend the same role rather than spawning new ones.

**Stays with orchestrator + user (judgment-dense)**: ADRs, design
docs, methodology articles, README, user-manual "what to say" sections.

**Delegated to `scribe`**: journal, BUILD_LOG, troubleshooting,
user-manual operational steps.

### D2. `spec_writer` stays shadow-mode through 1.0. Do not promote.

Economic analysis (1.0 scoping session, 2026-05-19) showed
`spec_writer`'s realistic per-task saving — after accounting for
orchestrator's mandatory review of the rendered spec, failure-and-
redispatch overhead, and patch overhead — is ~27% on Maestro's most
expensive orchestrator stage. Absolute: ~$0.08 per task, ~$8 per
100 tasks.

Against this saving, promotion adds:

- A 7th MCP tool surface
- A new artifact type ("decision sheet") with format conventions
- A third pipeline stage (decision-sheet → spec → coder), replacing
  today's two-stage spec → coder
- Doubled L5-protection failure surface — orchestrator must apply
  the anti-hallucination memory rules (`feedback_coder_spec_inline_signatures`,
  `feedback_api_failure_contract_explicit`, `feedback_worker_payload_completeness`,
  `feedback_verify_paths_before_spec`, `feedback_coder_full_file_diff_check`)
  in two places instead of one
- Contributor / future-Claude learning overhead

The complexity tax is paid permanently and compounds with every new
memory rule; the saving is small and linear. Borderline positive on
dollars, fragile on quality — L5 anti-hallucination discipline erodes
silently if orchestrator's spec review slips.

Promotion is reconsidered when **either** trigger fires:

- Opus context window becomes the orchestration bottleneck (measurable
  as ≥30% of dispatch sessions hitting auto-compression or run-out)
- Annual task volume crosses 1,000, making the $0.08/task linear
  saving compound to a meaningful absolute

### D3. The 1.0 cost lever is reviewer-payload contract-sheet adoption.

Reviewer payload construction (orchestrator stage 5) currently requires
verbatim file content per memory `feedback_worker_payload_completeness`.
This is ~$0.23 per task in Opus output cost.

T8.4 introduced an exception: shared upstream contracts may be
referenced as `docs/contracts/<scope>.md` plus a last-verified
commit-sha anchor. Adoption has been partial — applied where
convenient, not systematically.

For 1.0: make contract-sheet referencing the **default** for
upstream-shared contracts in reviewer payloads; verbatim becomes the
documented exception for novel content under review.

Expected saving ~40–50% on stage 5 with:

- No new role
- No new pipeline stage
- A quality risk (stale contract sheet) that the commit-sha anchor
  already mitigates

This is preferred over D2 because: same-magnitude saving, zero
architectural complexity tax, builds on existing pattern.

## Consequences

- `scribe`'s schema (currently leaks GitHub-issue workflow via
  required `issue_number` / `title` / `body`) must be reworked under
  #72 to accept `content_type` + per-type input fields. `scribe`'s
  role surface widens; its model and dispatch path unchanged.
- `spec_writer` stays in `maestro/tools/spec_writer.py` shadow but
  is not promoted in `docs/governance.md`'s "promoted roles" list.
  Memory `feedback_shadow_mode_active` continues to record it as
  shadow.
- Reviewer-payload playbook gets a documentation pass: contract-sheet
  referencing becomes the documented default, verbatim becomes the
  documented exception. Memory `feedback_worker_payload_completeness`
  updated to match.
- v1.0 worker roster: **4 promoted** (`coder` / `reviewer` / `scribe`
  / `librarian`) + **2 shadow** (`spec_writer` / `verifier`). No 7th
  role added.

## Alternatives considered

- **Open a 5th "writer" / "author" role** for journal / methodology
  rendering. Rejected: methodology stays with orchestrator (D1
  boundary); the residual rendering surface doesn't justify a new
  role's complexity tax; same-shape work already lives in `scribe`.
- **Promote `spec_writer` with rendering-only scope** (decision sheet
  → `spec_writer` renders → orchestrator reviews). Rejected: full
  overhead accounting showed only ~27% saving; L5 anti-hallucination
  discipline becomes a double-maintenance surface; borderline value
  not worth the complexity tax pre-1.0.
- **Defer the cost-lever question entirely to v1.x**. Rejected: 1.0's
  existence statement implies a cost story; contract-sheet adoption
  is low-complexity enough to land inside the 1.0 window.
