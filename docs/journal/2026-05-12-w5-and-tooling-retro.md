# 2026-05-12 (evening) — Epic 3 W5 closed; tooling retro → Epic 8 opened

> Long arc: started W5 in the afternoon after the morning's W1→W4
> journal landed. 3 UI tasks (T3.7 history / T3.8 live / T3.9 problem
> panel) dispatched in parallel; all 3 merged into v0.0.3 by evening.
> Mid-flight token-consumption analysis turned into a tooling
> retrospective: identified ~25% session-token waste, designed
> spec-writer + verifier + librarian-extension to close it. Epic 8 #78
> opened. First `docs/contracts/<scope>.md` landed as the prerequisite
> pattern. W-level cross-cutting reviewer experiment ran for the first
> time and immediately earned its keep — caught 3 cross-task
> consistency issues the per-task reviewers missed, including one that
> overturned a fail-verdict dismissal I'd been about to apply.
>
> Distinctive moments today: the title-suffix English-leak finding from
> T3.8 reviewer that I almost dismissed as a model fluke → W-level
> reviewer re-framed it as project convention inconsistency (`Maestro · X`
> not `X — Maestro`) → fix applied to all 3 W5 templates plus
> documentation in the contract sheet so it doesn't recur; the
> path-type miss + RoleId Literal miss in coder specs that triggered
> ~4k tokens of test-failure returns work, which became the concrete
> case study for proposing the verifier worker; the user pushing back
> on initial tooling proposal because schemas leaked Maestro-workflow
> concepts ("input里面不能有和当前工作流相关的任何内容"), forcing a
> clean shipped-user-first redesign.

## Session arc

Single afternoon-evening session continuing on `v0.0.3` head `99b1d97`
(this morning's journal commit). W5 started, completed, and got a
tooling-retro chaser. v0.0.3 head advanced `99b1d97 → 1b648e7`.

Cumulative across all closed tasks (43+ now): per-task economics in
`docs/data/dispatch-log.jsonl`; W5 telemetry added in chore commit
`d56790d`.

## Done

### W5 dispatch arc — T3.7 + T3.8 + T3.9 parallel

**Orchestration**: 3 UI tasks file-disjoint, upstream all stable
(T3.1-T3.6 closed yesterday + this morning). Parallel dispatch plan:
4-item decomposition audit clean; one shared label table negotiated
with user up front (✓成功 / ✗失败 / ⊘已拒绝 / ↩已降级 / ◐进行中 +
column headers + CTA copy); 4 librarian dispatches in parallel for
upstream contracts (events.py + reader.py + dispatch_log_api.py +
scaffold_view.py); 3 coder dispatches in parallel.

**T3.7 (#48) history view** — `maestro/webui/history_view.py` +
`templates/history.html` + 9 tests. One-shot scan of dispatch.jsonl,
events folded by request_id into HistoryRow dataclass with status
icon + Chinese label + role/member + model + duration + cost +
summary columns; `<details>`-based drill-down for full input/output
+ error/validation details; fallback events attach `↩ 已降级` badge
to matching request's row. Reverse-chronological by timestamp_iso.

**T3.8 (#49) live execution-flow view** — `maestro/webui/live_view.py`
+ `templates/live.html` (with ~80 lines inline vanilla JS) + 5
skeleton-render tests. Browser-native `EventSource` subscribes to
`/api/dispatch_log/stream` (T3.6); two zones (Running / Completed);
elapsed-time tick via `setInterval(1000)`; client-side event
dispatcher routes by `event_type` (start → Running card, end/failed
→ move to Completed, fallback → annotate badge with pendingFallbacks
Set holding out-of-order fallbacks, refused → directly Completed,
rotated → clear Running). htmx hx-sse rejected because per-event-type
handlers needed; vanilla JS allowed per ADR-0002.

**T3.9 (#50) problem panel** — `maestro/webui/problem_panel.py` +
`templates/problem_panel.html` (with 4-line vanilla JS ack handler) +
9 tests. Three categories: 失败的调度 / 团队配置被拒 (CTA →
/team) / 团队配置缺失（降级） (CTA → /wizard, grouped by
role+fallback_model). Per-session ack toggles `.acked` class
(opacity:0.4); no persistence by design.

**Integration bugs caught + fixed**:
1. `paths.dispatch_log_path(Path.cwd())` returns the **logs directory**,
   not the file. Coders treated it as a file path → `IsADirectoryError`
   on first test run. Fix: append `/ "dispatch.jsonl"` everywhere.
2. `RoleId` is `Literal["coder","librarian","reviewer","scribe"]` —
   not a free string. Tests built events with `role="junior"` /
   `"senior"` / `"editor"` etc. → Pydantic ValidationError. Fix:
   11 × `Edit replace_all` across 2 test files.
3. `from maestro.webui import templates` at module top resolves to the
   `templates/` SUBDIRECTORY (namespace package) instead of the
   `Jinja2Templates` instance, because pytest collection registers the
   subdirectory in `sys.modules`. Symptom: only fails when running the
   full test suite (when other tests pollute sys.modules first), not
   when running the new tests in isolation. Fix: late-bind import
   inside each view function (matches existing scaffold_view pattern).
   Documented in `docs/contracts/epic-3.md` § 8 with permanent-fix
   candidate (rename `templates/` to `jinja/`) deferred to v0.0.4.

**Task-level reviewers**: T3.7 pass (2 low findings dismissed);
**T3.8 fail** (medium, title contains "— Maestro" English); T3.9 pass
(1 low finding). I almost dismissed T3.8 as a fluke because T3.7 and
T3.9 reviewers passed identical `X — Maestro` patterns. Decision
deferred to user.

**W-level cross-cutting reviewer experiment**: dispatched one
additional reviewer with all 3 PRs' final state + spec asking for
cross-task consistency audit. Verdict: `concerns` × 3 medium + 2
concerns. Most important finding: **title-suffix order inverted vs
project convention**. `index.html` uses `Maestro · 本地 AI 软件团队`
(Maestro-first, middle dot, Chinese-after); all 3 W5 templates used
`中文 — Maestro` (Chinese-first, em-dash, Maestro-after). The
T3.8-fail wasn't "English leak in Chinese UI" — it was project
convention inconsistency. The fix is to flip all 3 templates to
`Maestro · 中文`, not to remove the brand name.

Also caught: `_format_time_iso` divergence (history hardcoded `Z`
suffix, problem_panel used `isoformat()`) and live view's completed
cards missing ✓/✗ icons that history showed. All 3 fixed in-place
before commit. Total W-level reviewer cost: ~8k tokens. Value: caught
3 real issues + overturned a dismiss decision. Earned its keep on
first run.

**Commits + merges**:
- `feature/48-t3-7-history-view` → merge `d9e3c13`
- `feature/49-t3-8-live-view` → merge `2c3020f`
- `feature/50-t3-9-problem-panel` → merge `cd20bc0`
- `chore(telemetry)` → `d56790d`
- Pushed v0.0.3 to origin: `08e7eed..d56790d`
- 3 feature branches deleted (per yesterday's auto-execute carve-out
  for merged local branches).
- Issues #48 / #49 / #50 closed with completion comments.

**Skipped scribe role for commit messages**. Hand-wrote 3 commit
messages. Rationale: per-commit scribe payload would have been ~5k
tokens × 3 = 15k for messages that take 100-200 tokens hand-written.
Decision logged here so the next session knows this was deliberate
optimization, not omission.

### Tooling retrospective → Epic 8 (#78) opened

Mid-W5, user asked "token 消耗也很多，结束后分析下". After scribe-skip
decision, did a full token-consumption analysis of the W5 wave
(~140k total). Identified ~36k recoverable (~25%) across:

- Reviewer payload triple-duplication of upstream contracts (~8k)
- Coder spec triple-duplication (~6-8k)
- Re-reading files I just wrote (~15k)
- 4 librarian dispatches that could be one (~10k)
- Coder reasoning section noise (~3-5k)
- Returns work from path-type / RoleId Literal misses (~4k)

User then asked about role / workflow gaps: "哪些可以委派给当前角色 +
哪些值得新角色". I proposed:

- **New spec-writer worker** (biggest gap): templates-heavy spec
  drafting moved from Opus to cheap-model Flash. Token-neutral in my
  context, but $$ savings + quality (verification checklist enforced
  in the worker prompt).
- **librarian extension** (single `file_paths` field): one round-trip
  for multi-file contract harvest.
- **New verifier worker tool**: claim-list → per-claim
  verified/incorrect/ambiguous. Catches RoleId / path-type misses
  before they become test failures.
- **W-level cross-cutting reviewer** (no new role, existing reviewer
  used differently).
- **Project-internal `docs/contracts/<scope>.md` convention**.

User pushed back on my first draft: tool input schemas were leaking
Maestro-workflow concepts (`issue_body`, `shared_constraints: <ref
to docs/contracts/epic-N.md>`). The lesson: shipped users will load
these tools in their own Claude Code sessions on their own projects;
schemas must be 100% generic. Revised: `task_description` (free-form),
`upstream_contracts: str` (free-form, caller assembles), no path
references, no Maestro-specific fields. `task_id` + `issue_number`
stay optional telemetry-only.

Filed as **Epic 8 #78** with 7 sub-tasks (T8.1–T8.7). Targets v0.0.4.
First Epic where spec-writer runs in shadow mode (orchestrator
hand-drafts AND dispatches in parallel; compare for 1-2 waves before
promoting). Issue body draft in `/tmp/v0.0.4-epic-issue.md` →
approved → created.

### docs/contracts/epic-3.md landed

408-line shared contract sheet for Epic 3 covering: 5 event models
verbatim, scan_log/tail_log/emit_event signatures with failure
contracts, paths.dispatch_log_path returns-directory gotcha,
dispatcher.run 3-state branching, SSE endpoint contract (event id
format, rotated synthetic event, reconnect semantics), shared UI
conventions (title pattern, status icons + Chinese labels, duration
format, cost format, time format, CTA targets), templates
name-collision gotcha with late-bind workaround, test conventions
(fresh app fixture + mock_cwd), v0.0.4 deferred list, update
protocol.

First instance of the `docs/contracts/<scope>.md` convention. T3.10
+ Epic 7 implementations will reference it directly. v0.0.4 spec-writer
worker will read it as `upstream_contracts` input.

Commit: `1b648e7`.

## Decided

- **Skip scribe for mechanical W5 commits**. Hand-written commit
  messages save ~15k tokens. Memory `feedback_shadow_mode_active`
  promoted scribe but doesn't make it MANDATORY for every commit;
  reviewer pass before merge IS mandatory; commit-drafting via scribe
  is a quality nice-to-have, not a DoD checkbox. v0.0.4 may revisit
  whether scribe should be opt-in per task.

- **W-level cross-cutting reviewer becomes default for parallel waves**.
  W5 proved value (caught 3 issues in one dispatch; overturned a
  T3.8 dismiss decision). Add to implementation-start protocol as a
  step between per-task reviewers and scribe / merge. v0.0.4 may
  formalize via skill update.

- **Project title convention now codified**: `Maestro · <中文>`
  (Maestro-first, middle dot, Chinese-after). All 3 W5 templates
  fixed; documented in `docs/contracts/epic-3.md` § 7. Future
  templates inherit.

- **Late-bind `from maestro.webui import templates`** inside each view
  function is the standard pattern until v0.0.4 renames the
  subdirectory. Documented in contract sheet § 8.

- **`paths.dispatch_log_path(...)` returns a directory**. Callers
  compose `/ "dispatch.jsonl"`. Documented in contract sheet § 4.
  Will become the first claim verified by v0.0.4 verifier worker
  in shadow-mode dogfooding.

- **RoleId is a Literal of {coder, librarian, reviewer, scribe}**.
  Documented in contract sheet § 1. Will be a verifier-mode claim.

- **Don't re-read files I just edited**. New workflow nicety to apply
  from W6 onward. Edit tool's success response is authoritative; my
  in-context tracking is the source of truth until the next test run
  refutes it. Saves ~15k per wave at current scale.

- **Generic-first tool schemas for v0.0.4**. No `issue_number` as
  required field anywhere; `task_id` / `issue_number` are optional
  telemetry-only. No file-path references to project-internal
  conventions (`docs/contracts/...`) in tool I/O. Caller assembles
  free-form strings; tool returns free-form output. This makes the
  tools usable by shipped users in their own Claude Code sessions on
  their own projects.

## Deferred

- **T3.10 (#51) end-to-end verification** — only remaining Epic 3
  sub-task. Single task, dependent on T3.7/8/9 (all done now). Will
  do curl-based smoke for the 2 `@pytest.mark.skip`'ed SSE streaming
  tests + verify all 3 surfaces render correctly with real dispatch
  events.

- **Typed dispatcher result** — T3.5b/T3.5c reviewers flagged
  `result.startswith("team.yaml at")` refusal detection as fragile.
  Carryover to v0.0.4.

- **SSE streaming unit tests** (T3.6) — 2 `@pytest.mark.skip`'ed
  pending httpx async client refactor.

- **Rename `maestro/webui/templates/` to `jinja/`** — permanent fix
  for the name collision. Separate v0.0.4 issue.

- **W-level reviewer skill formalization** — current usage is a
  manual dispatch with hand-written spec. v0.0.4 could add a
  parameterized cross-cutting-reviewer skill.

- **Index.html nav links** — `/history` / `/live` / `/problems`
  routes wired but not discoverable from the hero page. Defer until
  Epic 3 close or T3.10 decision.

- **Scribe revisit** — should scribe be required for non-trivial
  commits (e.g., body > 10 lines or change scope > 3 files)? Today's
  skip was the right call for formulaic feat commits; not obviously
  right for refactors or bug fixes. v0.0.4 retro.

## Handoff for next session

- **Branch state**: `v0.0.3` head `1b648e7`. All W5 feature branches
  deleted locally. Clean working tree.

- **445 tests passing + 2 skipped** (was 411 + 2 yesterday morning;
  +23 W5 tests + W-level fixes preserved green). Note: full run takes
  ~10s.

- **Open issues at session end**:
  - **Closed today**: #48 T3.7, #49 T3.8, #50 T3.9. 3 closes.
  - **Filed today**: **#78 Epic 8 [v0.0.4]: workflow tooling**
    (librarian extension + verifier + spec-writer).
  - **Still open in Epic 3**: only T3.10 (#51) end-to-end verification.
  - **Other open**: #72 (scribe schema leaks GitHub workflow, v0.0.4
    candidate — may merge into Epic 8 or stay separate), #74 (CLAUDE.md
    sanitize, v0.0.4), #15 (Epic 3 parent, ready to close after T3.10
    + savings refresh), #16 (Epic 4 packaging deferred), #11 (v0.0.3
    vision), #65 (Epic 7) + #66–#70 (Epic 7 sub-issues), #17/#18
    (governance migration tasks).

- **v0.0.3 release candidates progress**:
  - Epic 0 ✅, Epic 1 ✅, Epic 2 ✅
  - **Epic 3** — 9/10 sub-tasks done; T3.10 remains; close after that
    + savings refresh.
  - Epic 7 (Web UI savings page) — open, T7.1–T7.5 untouched.

- **Memory entries written / updated today**: none new today. Two
  candidates for v0.0.4 (per Epic 8 #78 S6):
  - `feedback_librarian_for_spec_reading.md` — add <100-line single
    file exception.
  - `feedback_worker_payload_completeness.md` — add stable-
    contract-sheet reference exception.

- **Watchpoints carried forward**:
  - **W-level cross-cutting reviewer pattern** is new. Watch how it
    behaves across different wave shapes (parallel-3 today; will
    parallel-N or wave with sequential dependencies work the same?).
  - **Per-pytest-collection sys.modules pollution** for the
    `templates/` subdirectory — the late-bind workaround is robust
    locally; remains to verify on CI when v0.0.3 lands somewhere with
    its own test infra.
  - **Title convention drift** — if a v0.0.4 feature adds a new
    template, it must follow `Maestro · X`. Contract sheet documents
    this but enforcement is on the author. v0.0.4 W-level reviewer
    will continue catching drift.

- **Next implementation candidates**:
  1. **T3.10 (#51)** — Epic 3 e2e verification + Epic 3 close. Final
     piece. Probably 1.5-2h. Includes curl smoke for SSE.
  2. **Epic 3 close** — parent #15 close + `docs/savings.md` refresh
     per `feedback_savings_refresh_per_epic`. Mechanical after T3.10.
  3. **Epic 7** wave 1 — T7.1 (calc core extract) + T7.2 (group_by_time
     + resolve_log_path); both independent foundation tasks.
  4. **Epic 8** kickoff — preliminary scoping wave for librarian
     extension + verifier scaffold. Most reusable across remaining
     v0.0.3 and all of v0.0.4.

## Process learnings

- **Token analysis IS work**. Mid-W5 the user requested a token
  analysis; that analysis directly produced Epic 8. Without the
  retrospective, the same workflow inefficiencies would have
  recurred every subsequent Epic. Lesson: schedule retros at natural
  break points (every Epic close minimum); don't wait for "wrap up"
  signals.

- **W-level reviewer is high-ROI**. Single ~8k-token dispatch caught
  3 real consistency issues in W5 — issues that would otherwise
  have either shipped (UX papercut) or required follow-up PRs. The
  per-task reviewers had no way to see cross-task because their
  payloads are scoped to one task. Default-on for parallel waves
  going forward.

- **Skip-scribe-for-mechanical-commits is legitimate**. 15k tokens
  for messages I can write in 200 tokens is a 75× false economy.
  Memory `feedback_shadow_mode_active` doesn't make scribe mandatory
  for commits; the reviewer-pass-before-merge rule is the actual
  DoD. Adjust expectations: scribe is a quality tool for non-trivial
  commits, not a process tax.

- **User's "input不能有workflow-specific" pushback was load-bearing**.
  My first v0.0.4 tool proposal had `issue_body` + `docs/contracts/`
  references baked in. User caught it. The result is a much cleaner
  shipped tool surface that doesn't bleed Maestro internals to
  shipped users. Lesson: when designing tool schemas, explicitly ask
  "would this make sense for a user with a Vue + Postgres project
  asking the same kind of question?" If not, the field is leaking.

- **Per-task reviewer fail verdict is not always correct**. T3.8
  fail on title-suffix was technically a real issue, but the
  reviewer's interpretation ("English in Chinese UI") was the wrong
  frame. The actual issue was "project convention inversion".
  Without W-level second opinion, I would have either dismissed the
  fail (wrong) or applied an over-narrow fix (only T3.8, leaving T3.7
  and T3.9 inconsistent in the opposite direction). The W-level
  reviewer's broader view found the right answer. Per memory
  `feedback_issue_close_requires_full_DoD`: reviewer fail without
  fix-or-re-pass should block close. The W-level pass + fix-applied
  satisfies that strictly.

- **Three-issue split (T3.7 / T3.8 / T3.9) parallel pattern
  validated**. Same shape as W4's T3.5a/b/c split. Today's wave
  finished in one session (afternoon-evening); W4 took most of a
  session for ~the same volume. Wave shape: 1 spec round + 1 coder
  round + 1 reviewer round + 1 W-level round + 1 commit/merge round.
  Each round is parallel-3.

- **Coder reasoning section noise**. ~1-2k tokens per coder return
  is reasoning narrative I never reference. v0.0.4 spec-writer-
  authored specs will include `omit <reasoning>` directive by
  default. Mechanical efficiency.

- **The auto-execute carve-out for local merged-branch cleanup is
  working**. Today's `git branch -d feature/48 feature/49 feature/50`
  ran without approval and was unambiguous. The earlier-today
  carve-out (yesterday's evening update to
  `feedback_github_approval.md`) successfully reduced one
  approval-turn per task.
