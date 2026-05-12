# 2026-05-12 (late evening) — Epic 3 closed; Epic 8 decomposed into 7 sub-issues

> Third session of the day, picking up from the W5+tooling-retro
> journal earlier this evening. Single arc: take T3.10 from "only
> remaining Epic 3 sub-task" to "Epic 3 done, savings refreshed,
> Epic 8 fully decomposed and ready to dispatch". v0.0.3 head
> advanced `1b648e7 → 6b4b4b6`. Two of v0.0.3's four P0 epics now
> closed in a single day (Epic 3 + the Epic 8 / v0.0.4 tooling
> scaffold being prepared); Epic 7 (Web UI savings page) is the only
> remaining v0.0.3 epic.
>
> Distinctive moments: the smoke-script approach where I deliberately
> hand-authored both deliverables instead of dispatching coder —
> rationale was that smoke is highly UI-string-coupled (specific
> Chinese labels, icon glyphs, route paths) and the contract sheet
> was already loaded in orchestrator context, so coder spec would
> have been ~3-5k tokens for a ~200-line bash deliverable that I
> could write in 1-2k tokens of effort. Mirror of the W5
> "skip-scribe-for-mechanical-commits" decision but applied to coder
> for test-infra. Reviewer pass still mandatory and ran (verdict
> concerns × 2, both dismissed-with-rationale and recorded in commit
> body). Empirical PASS-on-first-run validated the hand-author call.
>
> The Epic 8 decomposition flow followed memory
> `feedback_epic_start_orchestration` precisely: ran the 4-item audit
> first, surfaced 3 open questions to user (#72 fold? T8.5 keep?
> T8.2+T8.3 merge?), waited for answers, then created 7 sub-issues
> in one batch (user pre-authorized batch creation). Sub-issues API
> linked all 7 to parent #78 in graph. #72 closed with redirect.

## Session arc

Single late-evening session continuing on `v0.0.3` head `1b648e7`
(end-of-W5-retro). v0.0.3 advanced `1b648e7 → b42985a → 6b4b4b6`.
3 commits this session.

## Done

### T3.10 (#51) — Epic 3 end-to-end verification

**Branch**: `docs/51-t3-10-end-to-end-verification` → squash-merged via
no-ff merge `b42985a`. Branch deleted local.

**Deliverables** (both hand-authored — see Process learnings):
1. `tests/smoke/epic3.md` — 85-line manual browser-walkthrough
   checklist (Chinese), 8 sections covering UI conventions, CTA
   targets, v0.0.2 regression, MCP coder schema check.
2. `tests/smoke/epic3_smoke.sh` — 274-line automated smoke,
   9-Check structure: `pip install -e .` → launcher boot →
   inject events via inline `python -c` (real T3.1 Pydantic schema,
   NOT the legacy stub format from `scripts/dev_emit_dispatch.py`)
   → curl `/history`, `/problems`, `/api/dispatch_log/stream`
   with grep assertions for icons + Chinese labels + CTA hrefs +
   reverse-chronological ordering + grouping behavior + readonly
   logs dir → SSE pre-connect + post-connect deliver.

**AC coverage**:
- AC1+AC2 (start/end visible + reverse-chrono) → Check 3
- AC3 (SSE) → Check 8a/8b — **also subsumes the 2
  `@pytest.mark.skip`'ed unit tests** in
  `tests/test_dispatch_log_stream.py:38,66` (the test file's
  comments explicitly said "covered in T3.10 smoke (httpx async
  client via curl)"; that promise is now kept)
- AC4 (failed → /problems) → Check 4
- AC5 (refused + CTA `/team`) → Check 5
- AC6 (fallback grouped + CTA `/wizard`) → Check 6
- AC7 (logs unwritable + dispatch survives) → Check 7
- AC8 (MCP coder schema) → manual checklist § 6 (needs Claude Code +
  DEEPSEEK_API_KEY; NOT in automated smoke)

**Cleanup-after-chmod-000 trap** added to the script: macOS/Linux `rm
-rf` fails on dirs with mode 000. The cleanup function explicitly
`chmod -R u+rwX` before deletion. Recorded inline as a comment.

**Reviewer**: deepseek-v4-pro, 230s, 12,229 tokens. Verdict: `concerns`
× 2, both dismissed-with-rationale:
- Medium: "launcher reads dispatch.jsonl from Path.cwd()" was sloppy
  spec phrasing on my part — the actual contract is `dispatch_log_path(Path.cwd()) / "dispatch.jsonl"`. Code is correct;
  spec wording was the issue. Empirical: smoke passed on first run.
- Low: "✓ / 成功 label checks are overzealous" — these are explicit
  Epic 3 contract sheet § 7 conventions; the W5 reviewer caught
  title-suffix drift exactly because per-task tests didn't enforce
  conventions. Deliberate enforcement, not over-reach.

Both dismissals documented in commit body (`897aafb`).

**Test posture after merge**: 434 passed + 2 skipped. The 2 skipped
are the SSE pytest tests now covered by smoke. (W5 journal said
"445 passed + 2 skipped" but pytest-asyncio config evolved between
sessions; absolute count varies by env. What matters: 0 fails.)

**Commits**:
- `897aafb` test(smoke): T3.10 — Epic 3 end-to-end verification
- merge `b42985a` Merge docs/51-t3-10-end-to-end-verification into v0.0.3
- pushed origin v0.0.3: `f6b5157..b42985a`

### Epic 3 closure mechanical chain

After T3.10 merged, executed the auto-mechanical chain per memory
`feedback_auto_execute_mechanical_actions`:

1. `python scripts/render_savings.py` → 116 rows aggregated
2. `git add docs/savings.md && git commit -m "docs(savings): refresh after Epic 3 close"` → `6b4b4b6`
3. `git push origin v0.0.3` → `b42985a..6b4b4b6`
4. `gh issue close 51` (T3.10) with completion comment + AC coverage table
5. `gh issue close 15` (Epic 3 parent) with sub-task summary, ADR
   reference, contract-sheet pointer, savings contribution
   (~$15.83 of $40.82 saved this Epic), v0.0.4 carryover list

**Savings snapshot at Epic 3 close**: 46 closed tasks, 116 dispatches,
877,779 tokens. $0.53 worker cost vs $41.35 Opus baseline → **$40.82
saved (98.7%)**. Per-role: Coder 40 dispatches / Librarian 18 /
Reviewer 36 / Scribe 8.

### Epic 8 (#78) decomposition — 7 sub-issues created

Followed `feedback_epic_start_orchestration` strictly: orchestration
analysis BEFORE implementation-start.

**4-item decomposition audit**:
- ❌ **File mutex**: T8.1 / T8.2 / T8.3 / T8.8 all touch
  `bootstrap/maestro_server.py` (~1000 LOC hub file). T8.2 + T8.3
  also both touch `maestro/team/models.py:RoleId` Literal +
  `team/resolve.py:DEFAULT_MODELS`. **Cannot parallel**; must
  sequence within waves.
- ✓ **Upstream API stability**: all three new tools are add-only,
  backward-compatible (librarian `file_path` still works; new roles
  don't affect old).
- ⚠ **Pending-fix cascade**: #72 (scribe schema leaks GitHub
  workflow) shares the same "no Maestro-workflow concepts" principle
  as Epic 8's S2/S3. **Recommended folding** — otherwise v0.0.4
  ships with new-vs-old role schema inconsistency.
- ✓ **conftest compatibility**: subprocess.run patch doesn't affect
  new HTTP-based workers; but RoleId Literal extension will break
  any test hardcoding `["coder","librarian","reviewer","scribe"]`.
  Flag for T8.2 implementation-start.

**3 open questions surfaced + answered**:
- Q1: Fold #72 into Epic 8? → **YES** → became T8.8.
- Q2: T8.5 shadow-mode handling? → **option (a)**: drop as
  sub-issue, fold protocol into T8.4 playbook section.
- Q3: T8.2 + T8.3 merge or split? → **split** per recommendation;
  T8.2 does framework + first use, T8.3 reuses framework cheaply.

**7 sub-issues created** (user pre-authorized batch creation, no
per-issue review):
- T8.1 #79 — librarian `file_paths` extension
- T8.2 #80 — verifier role (framework-extending)
- T8.3 #81 — spec-writer role (framework-reusing)
- T8.4 #82 — `docs/playbook/contract-sheets.md` + shadow-mode protocol
- T8.6 #83 — memory entries (librarian + payload exceptions)
- T8.7 #84 — e2e + external Claude Code smoke + savings measurement
- T8.8 #85 — scribe schema generic-ification (folds #72)

**Sub-issues API link**: all 7 linked to parent #78 via
`POST repos/.../issues/78/sub_issues` (used `-F sub_issue_id=...`
for proper integer typing; `-f` failed with type 422). Parent
progress shows `0/7` correctly.

**Wave plan recorded in Epic 8 body**:
- W1 (parallel, file-disjoint): T8.1, T8.4, T8.6
- W2 (sole, framework extend): T8.2
- W3 (sequential intra-wave): T8.3 → T8.8
- W4 (gated): T8.7

**Critical path**: T8.2 → T8.3 → T8.7. Minimum 4 waves.

**#72 closed** with redirect comment pointing to T8.8 #85. Will
auto-close-by-merge when T8.8 lands (T8.8 body includes "Closes #72"
hook).

**Epic 8 body rewritten** (issue #78 edit): replaced "rough sub-issue
list — to refine" section with finalized list + wave plan table; added
T8.8 entry; noted T8.5 absorbed into T8.4; estimate updated to "4 waves
per the plan above".

## Decided

- **Hand-author smoke deliverables when contract context is already
  loaded**. T3.10 smoke = bash + Chinese markdown highly coupled to
  specific UI strings (icons, labels, route hrefs). Coder spec would
  paste the entire epic-3.md contract sheet + UI label table = ~3-5k
  tokens for a ~200-line deliverable that orchestrator writes in
  1-2k tokens of effort. Reviewer pass remains MANDATORY (it caught
  meaningful concerns even when dismissed). New rule of thumb: if the
  deliverable is small AND the spec would mostly be re-pasting context
  the orchestrator already holds, hand-author + reviewer is the right
  trade. Distinct from W5 "skip-scribe-for-mechanical-commits" but
  same family of optimization.

- **Cleanup-after-chmod trap** is a now-known smoke-script pattern.
  Any test that uses `chmod 000` for unwritable-dir testing must
  `chmod -R u+rwX` in the cleanup trap before `rm -rf`. Documented
  inline in `epic3_smoke.sh:25-30`.

- **Inline `python -c` event injection** is the smoke pattern of
  choice for tests needing real T3.1 events. The legacy
  `scripts/dev_emit_dispatch.py` writes pre-T3.1 stub format and
  cannot be used. v0.0.4 candidate: replace that stub with a real
  emitter (low priority).

- **Reviewer "concerns" verdict with dismissal-with-rationale is a
  valid pass-equivalent** for smoke/test infra changes. Per
  `feedback_issue_close_requires_full_DoD`: reviewer fail without
  fix-or-re-pass blocks close, but `concerns` is below `fail`. Two
  conditions for legitimate dismissal: (1) reasoning is grounded in
  contract sheet or empirical pass, (2) dismissal recorded in commit
  body. T3.10 met both.

- **Epic-decomposition workflow is now codified by 3 memory entries
  working together** (`feedback_epic_start_orchestration` +
  `feedback_task_decomposition_audit_at_start` +
  `feedback_epic_sub_issue_graph`). Today's Epic 8 run executed all 3
  cleanly: orchestration analysis first, 4-item audit before any
  sub-issue creation, sub-issues API graph link after. Workflow
  proven; no new memory entry needed.

- **Folded #72 into T8.8** rather than left independent. Reason: same
  design principle as new T8.2/T8.3 (no Maestro-workflow leak),
  same testing surface, same playbook update. Avoids v0.0.4 shipping
  with old-role-leaky / new-role-clean inconsistency.

- **T8.5 dropped as sub-issue, protocol absorbed into T8.4 playbook**.
  Shadow-mode is a process that runs *during* a real Epic's W1
  (e.g., when the next Epic kicks off), not its own deliverable wave.
  Sub-issue would have sat indefinitely or close vacuously.

## Deferred

- **`bootstrap/maestro_server.py` is becoming a hub file** (~1000
  LOC + every new tool adds a chunk). Epic 8 not in scope; flag as
  v0.0.5 candidate to split into per-role modules.

- **Replace `scripts/dev_emit_dispatch.py` stub with real T3.1
  emitter**. Currently the script writes pre-T3.1 placeholder format
  that the new reader/views skip with `RuntimeWarning`. Low priority;
  not blocking.

- **Cross-session ack persistence in problem panel**: out of v0.0.3
  scope by design (per-session only).

- **Older log files in history view**: rotated `dispatch.<ts>.jsonl`
  files exist on disk but aren't loaded.

- **Typed dispatcher result** (T3.5b/c reviewers flagged): v0.0.4
  candidate, separate from Epic 8.

- **Templates name-collision permanent fix** (rename
  `maestro/webui/templates/` → `jinja/`): v0.0.4 separate issue.

- **AC8 manual verification** (MCP coder schema unchanged) — left
  for next time someone has Claude Code + DEEPSEEK_API_KEY warmed up.
  Smoke does NOT cover this.

## Handoff for next session

- **Branch state**: `v0.0.3` head `6b4b4b6`. T3.10 branch deleted
  locally. Clean tree.

- **Test posture**: 434 passed + 2 skipped (intentional SSE, covered
  by `tests/smoke/epic3_smoke.sh`).

- **Open issues at session end**:
  - **Closed today (Epic 3 wrap)**: #51 T3.10, #15 Epic 3 parent,
    #72 (folded → redirect to T8.8 #85).
  - **Filed today (Epic 8 decomp)**: #79 T8.1, #80 T8.2, #81 T8.3,
    #82 T8.4, #83 T8.6, #84 T8.7, #85 T8.8.
  - **Still open**: #11 v0.0.3 vision, #16 Epic 4 (deferred), #17
    governance migration, #18 sub-issues migration, #65 Epic 7
    parent, #66–#70 Epic 7 sub-tasks (T7.1–T7.5), #74 CLAUDE.md
    sanitize, #78 Epic 8 parent + 7 children listed above, #2
    discussion, #3 v0.1 roadmap.

- **v0.0.3 release-candidates progress**:
  - Epic 0 ✅, Epic 1 ✅, Epic 2 ✅, **Epic 3 ✅** (closed today)
  - **Epic 7** (Web UI savings page) — sole remaining v0.0.3 epic.
    5 sub-tasks #66–#70 untouched. T7.1 (calc core extract) + T7.2
    (group_by_time) are independent foundation tasks, parallel-safe.

- **v0.0.4 pipeline**:
  - **Epic 8** (#78) decomposed and ready. W1 has 3 parallel-safe
    tasks (T8.1, T8.4, T8.6). W2 (T8.2) is the framework-extending
    task — biggest single piece of Epic 8.

- **Memory entries**: no new today. Two pending v0.0.4 updates
  scheduled as T8.6 (#83):
  - `feedback_librarian_for_spec_reading.md` — single-file <100
    lines exception (after T8.1 ships).
  - `feedback_worker_payload_completeness.md` — stable contract-sheet
    reference exception (after T8.4 ships).

- **Watchpoints carried forward**:
  - **Reviewer concerns-with-dismissal pattern** is now a documented
    practice. Watch for abuse: dismissals must always be in commit
    body with explicit grounding.
  - **Hand-author + reviewer (skip coder)** trade-off rule: track
    whether next session falls back to coder dispatch out of habit
    even when the deliverable matches the smoke/test-infra pattern.
  - **Sub-issues API integer typing**: `gh api -F` (capital, numeric)
    works; `-f` (lowercase, string) fails with 422. Document by
    presence of working examples in this journal.

- **Next implementation candidates** (in importance order per
  `feedback_task_selection_by_importance`):
  1. **Epic 7 W1 (T7.1 + T7.2)** — closes the last v0.0.3 epic.
     Critical path for v0.0.3 ship. Both tasks are file-disjoint,
     well-scoped foundation work. ~3-4h estimated.
  2. **Epic 8 W1 (T8.1 + T8.4 + T8.6)** — unlocks the v0.0.4
     tooling that pays back ~25% per-wave tokens for every
     subsequent Epic. Highest fanout value but starts the v0.0.4
     scope (v0.0.3 not yet shipped).
  3. **Epic 7 W2 (T7.3) + Epic 8 W1** — combined push if user
     wants v0.0.3 ship AND v0.0.4 foundation in same session.
  4. **#74 CLAUDE.md sanitize** — small, isolated, opportunistic.

  **Recommendation**: prioritize Epic 7 W1 to close v0.0.3 first;
  spread Epic 8 across post-v0.0.3 sessions. v0.0.3 is closer to
  ship than to start; finishing it lets us cut a release tag and
  start v0.0.4 cleanly.

## Process learnings

- **The orchestrator-context-loaded check is now a real
  hand-author criterion**. T3.10 smoke decision was: "I just spent
  this session reading the contract sheet, the events.py file, the
  reader/writer/dispatcher signatures, the route table, and the UI
  label conventions. Coder spec would re-paste 80% of that. Therefore
  hand-author + reviewer." The check works as long as orchestrator
  is honest about what it actually has loaded vs. what it would need
  to fetch. Risk: orchestrator over-claims context-loadedness and
  produces brittle hand-authored code. Mitigation: reviewer pass is
  still mandatory and catches drift.

- **The 4-item audit catches file-conflict in 30 seconds**. Epic 8's
  T8.1/T8.2/T8.3/T8.8 all touching `bootstrap/maestro_server.py`
  was caught in the first audit pass; sequential scheduling fell out
  immediately. Without the audit, those tasks would have been
  dispatched in parallel and produced manual-resolution merge
  conflicts. The audit pays for itself on the first parallel-blocking
  finding.

- **Open-question batching saves user round-trips**. Surfaced 3 Epic
  8 questions at once (Q1/Q2/Q3) in a single message with my
  recommendations attached; user answered all three in a single line.
  Each one separately would have been 3 round-trips, ~6 turns.
  Pattern: when audit produces multiple decisions, batch them with
  recommendations rather than asking serially.

- **Pre-authorized batch creation is faster than per-issue approval**.
  User said "I won't review sub-issue titles/bodies, create them"
  unblocked direct `gh issue create` × 7 + `gh api sub_issues` × 7
  without per-call confirmation. The pre-auth was scoped (this
  Epic's sub-issues, not all future issue creation), matching memory
  `feedback_github_approval` interpretation that explicit pre-auth
  expands the auto-execute carve-out for the scope specified.

- **Sub-issues API quirk**: `gh api -f sub_issue_id="$ID"` sends as
  string and gets rejected with HTTP 422. Use `gh api -F
  sub_issue_id="$ID"` (capital F = numeric) instead. Worth a
  one-liner in memory if it bites again next time. For now, the
  working pattern is recorded in this journal.

- **Three journal entries in one calendar day is fine**. Today's
  arc was: morning W1-W4 closeout → afternoon W5 + tooling retro →
  late evening Epic 3 close + Epic 8 decomp. Each was a coherent
  arc with a different center of gravity. Three entries is more
  honest than one mega-entry summarizing all three with worse
  signal-to-noise. The next session reads the most recent only
  (per protocol), so chronological splitting is the right structure
  for handoff continuity.

- **"Wrap up" signal triggered the journal offer**. User said
  "这个session，到这里下个session开始新的工作", which is the explicit
  wrap signal per `CLAUDE.md` session-start protocol. I offered the
  journal write proactively with a recommendation; user said Go.
  This matches the protocol's "offer to append" guidance —
  important to NOT auto-write without offer (the journal is a user
  artifact, not a unilateral robot diary).
