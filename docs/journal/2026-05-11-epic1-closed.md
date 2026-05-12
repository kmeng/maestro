# 2026-05-11 — Epic 1 Closed

> One arc, one day, 8 task PRs (T1.1–T1.8). Epic 1 (#13) parent closed.
> Sibling to `2026-05-10-epic0-closed.md` (Epic 0 closed yesterday). The day's
> distinctive moments: a pre-T1.1 doc realignment PR catching a stale design
> spec, reviewer promoted out of shadow mid-epic, two corrections to the
> "coder modifications" feedback memory (the second one fundamental), and
> the late decision to add T1.8 — promoting Epic 1's dispatch lessons from
> personal memory to a shippable Orchestration Playbook at `docs/playbook/`.

## Session arc

Started on `v0.0.3` head `ea0e061` (Epic 0 closed last night). Goal: close as
many Epic 1 tasks as possible. Realistic stretch goal: close the Epic.

Result: Epic 1 closed in one day. 8 tasks merged, `v0.0.3` head moved from
`ea0e061` to `2137571`. Worker fleet dispatched 13 times (8 coder, 5 reviewer
— skipped reviewer on T1.7 smoke and T1.8 playbook where it doesn't apply).
Per-task economics tracked in `docs/savings.md`; cumulative across 23 closed
tasks: **$13.86 saved (98.7%)** vs Opus-baseline.

## Done

### Pre-T1.1: scribe schema bug filed + design realignment

- **[#72](https://github.com/kmeng/maestro/issues/72) — scribe schema bug
  filed for Epic 5 (v0.0.4 backlog)**. Out of v0.0.3 scope; surfaced during
  T6.8 design and held in personal memory; today promoted to a tracked
  GitHub issue. Body lays out the scope (4-role audit, possible directions,
  decision deferred) so v0.0.4 has a concrete starting point.

- **Design realignment PR (`docs/26-realign-team-schema-with-epic5-roles`,
  commit `34827a3`, merge `e9dda6f`)**. Before writing any T1.1 code, caught
  that ADR-0004 + design 13 + README all described a hypothetical PM/Senior/
  Junior/Documentarian team — but Epic 5 had landed coder/librarian/reviewer/
  scribe with deepseek-v4-pro/-flash as the actual fleet. User confirmed
  interpretation A (team.yaml roles = worker fleet). Updated ADR-0004 with
  a Revisions section, rewrote design 13's data-model / validation / failure
  / acceptance sections, updated README's "How it works" diagram + "The team"
  + Quick Start + FAQ. Plus the bodies of issues #26 / #29 / #31 (the T1.x
  tasks that referenced the stale roles). 3 commits in one PR; no code.
  Effort: ~30 min but unblocked everything downstream.

### T1.1 (#26) — Pydantic team config models + DEFAULT_MODELS

Branch `feature/26-team-pydantic-models`, commit `795e02d`, merge `fc8a52d`.
- `maestro/team/__init__.py` + `maestro/team/models.py` — `TeamConfig`,
  `RoleEntry`, `RoleId` (Literal of 4), `ROLE_IDS` tuple, `DEFAULT_MODELS`
  dict (coder/reviewer → deepseek-v4-pro; librarian/scribe → deepseek-v4-flash).
- Validators per design 13 D2: member strip + ≤64 chars + no control chars
  (anywhere — including positions strip would discard); model regex + ≤128 +
  strip; schema_version == 1; role-set equality; member alias uniqueness
  case-insensitive + whitespace-trimmed.
- 27 tests (22 functional + 5 parametrized expansions).
- Coder dispatch (`deepseek-v4-pro`, 132s / 7163 tok) produced 26 of the
  tests; reviewer (152s / 9629 tok, shadow mode at this point) caught a
  logically self-contradicting assertion in
  `test_duplicate_member_alias_rejected_whitespace_insensitive`. Both
  orchestrator + reviewer agreed on the fix; severity differed (reviewer
  high, orchestrator medium). One orchestrator-side spec-precision drift
  fixed inline: the member control-char check needed to run on raw input,
  not stripped value (`Cody\n` should be rejected even though strip would
  remove `\n`).
- `pyproject.toml` bumped to add explicit `pydantic>=2` dep (was transitive
  via fastapi).
- Full suite green: 175 → 27 new = 175 still passing + 27 new.

### T1.2 (#27) — YAML read/write helpers + atomic write

Branch `feature/27-team-yaml-io`, commit `c965297`, merge `750c0cb`.
- `maestro/team/io.py` with three-state `load_team_config` (returns `None` /
  `TeamConfig` / `TeamConfigInvalid` typed wrapper, the wrapper carrying the
  Pydantic error when validation failed, distinguished from YAML parse
  failure where `pydantic_error is None`) and atomic `save_team_config` via
  `os.replace` write-then-rename helper. Chinese header comment block per
  design 13 D6.
- 13 tests covering: absent / round-trip / mkdir / header / yaml parse
  error / validation error / unknown role / empty file / top-level list /
  os.replace usage / save-failure preserves original / save-failure cleans
  tmp / overwrite-existing.
- Wired into `bootstrap/maestro_server.py` startup as a no-op probe.
- Coder dispatch (196s / 9546 tok) produced `io.py` + tests cleanly, but
  also produced inferred-stub versions of `maestro/team/__init__.py` (would
  have dropped existing exports) and `bootstrap/maestro_server.py` (replaced
  the 1582-line server with a 60-line stub). Coder concerns flagged the
  inferences honestly. Orchestrator handled both modify-existing files
  surgically via Edit; coder's clean parts (io.py + tests) used as-is.
- First version of `feedback_coder_file_modification.md` written
  after this — the wrong version. Logged as "carve modifications out to
  orchestrator" — corrected later in the day.
- Full suite: 188 passed.

### T1.3 (#28) + T1.6 (#31) — parallel dispatch

Branches `feature/28-team-http-api` (commit `d80f1be`, merge `b20a5d9`) and
`feature/31-worker-team-resolve` (commit `1474fad`, merge `16e495c`).

- **T1.3** — FastAPI APIRouter `maestro/webui/team_api.py` with
  `GET /api/team` (404 absent / 200 valid / 422 invalid with structured
  detail list + reason string) and `POST /api/team` (201 on save, 422 on
  Pydantic validation). `_format_invalid_detail` helper translates the
  T1.2 `TeamConfigInvalid` into FastAPI's per-field error shape. 11 tests
  via TestClient + monkeypatched `_project_root`.
- **T1.6** — new `maestro/team/resolve.py` with `resolve_role_model` and
  `ResolveOk`/`ResolveRefuse` discriminated union. Plus orchestrator
  surgically edited each of `_coder_impl`, `_librarian_impl`, `_reviewer_impl`,
  `_scribe_impl` in `bootstrap/maestro_server.py` to call the resolver at
  the top of each handler and use the resolved `model` local everywhere
  `MODEL_PRO` / `MODEL_FLASH` had been hardcoded. Added a tiny
  `_emit_team_event` helper that appends to `logs/team_events.jsonl`
  (best-effort; T3.1 will replace with proper Pydantic event models).
  16 unit tests (resolve.py) + 9 integration tests (bootstrap-side helpers
  + per-handler refusal path).
- Both dispatched in parallel (T1.3 coder 104s / 5609 tok; T1.6 coder
  109s / 5816 tok). Then reviewer dispatched on T1.3 right away (pass,
  zero findings); orchestrator handled bootstrap edits for T1.6 manually
  per (then-current) "modifications by orchestrator" feedback memory.
  Then reviewer on T1.6 (also pass). T1.3 landed first (smaller, no
  bootstrap touch); T1.6 landed second.
- **Promoted reviewer out of shadow mode** after this batch. User
  signalled: "reviewer 的运行结果还不错，后面就采用 reviewer 的结果，
  你就不用再重复 review 了，除非有必要". Updated
  `feedback_shadow_mode_active.md` accordingly.
- Full suite after T1.3 + T1.6: 224 passed.

### Corrected `feedback_coder_file_modification.md` (fundamental rewrite)

User pushback: "你说新文件是 coder 来做，修改自己来干，我是不认同的。那
我们就失去了这个项目的意义，毕竟修改是大多数。一定是 coder 优先". The
old version of the memory recommended orchestrator-handled modifications
as the default — fundamentally backwards for a project whose value
proposition IS dogfooding modifications onto the worker fleet.

Rewrote the memory: **coder is the default for every code change including
modifications. The fix for "coder can't see the file" is to include the
file's full content in the spec, NOT to carve modifications out to the
orchestrator.** Locked in for the rest of the day.

This correction echoed forward: T1.4 / T1.5 / T1.7 all dispatched coder
on existing-file modifications (via embedding the file content in spec),
not orchestrator-fixing them.

### T1.4 (#29) + T1.5 (#30) — parallel dispatch (UI tasks)

Branches `feature/29-team-wizard-ui` (commit `8db6aec`, merge `ea5dfaa`) and
`feature/30-team-catalog-view` (commit `9eaaf1e`, merge `5e5e87f`).

- **T1.4 wizard** — `maestro/webui/wizard.py` + 6 Jinja templates
  (wizard.html shell, step1–4 partials, wizard_field_error.html). 4-step
  flow per design 13: Welcome → Role tour (form with 4 role rows, inline
  field validation on blur via htmx) → Confirm → Done. Chinese copy. 10
  tests via TestClient.
- **T1.5 catalog** — `maestro/webui/team_catalog.py` + 2 templates
  (team_catalog.html main page + team_catalog_row.html partial). State-
  aware banners (missing / invalid / valid). Per-row htmx outerHTML swap
  for edit-in-place. 8 tests.
- T1.4 dispatch was the largest of the day: coder 408s / 17231 tok
  (6 templates + router + tests + modify __init__.py). Three coder bugs
  caught by orchestrator and fixed: (a) `_existing_or_default` used
  attribute access on TeamConfig.roles (it's a dict, not attr); (b)
  hardcoded version placeholder `"0.0.3"` instead of `maestro.__version__`;
  (c) the import-by-name monkeypatch trap (changed `from team_api import
  _project_root` to `from maestro.webui import team_api` so monkeypatching
  reaches the call site). Reviewer flagged a high-severity finding that
  turned out to be a false positive (didn't account for T1.1's
  `_validate_member` stripping internally) plus a valid low (template
  consistency); applied the low, rejected the high with rationale.
- T1.5 had two issues: first coder dispatch produced an empty `<output>`
  block (format failure). Re-dispatched with a format reminder. Second
  dispatch succeeded (159s / 10052 tok). Then two orchestrator-side
  fixes outside coder's scope: (a) starlette `TemplateResponse` new-API
  switch (was `(name, context)` form — triggers Jinja LRU "unhashable
  type: dict" error in newer starlette; new form is `(request, name,
  context)`); (b) same import-by-name monkeypatch fix as T1.4.
- Full suite after T1.4 + T1.5: 242 passed.

### Mid-epic strategic discussion + T1.8 created

User asked three questions: (1) what consumed the most tokens, (2) how to
improve reviewer accuracy, (3) why orchestrator wrote tests sometimes
(spotted me writing `tests/test_worker_team_resolve.py` myself).

Answers summarized:
- Tokens: orchestrator-written specs + orchestrator-written code/tests +
  long progress updates dominate. Worker dispatches are the smaller share.
- Reviewer accuracy: context problem, not model-capability problem. Fixed
  by including cross-module reference code + test-results in the reviewer
  spec.
- Tests: yes, sometimes orchestrator wrote them. Wrong. Promised to
  dispatch coder for tests too.

Follow-up question about TDD: would it help correctness? Answer: yes for
logic-heavy work (data models, validators, dispatchers, I/O contracts),
no for templates / UI / smoke / docs. Adopt selectively.

Then the deeper question from user: "我的 memory 里这些经验，其他用户用
Maestro 时怎么办？" — the recognition that the lessons being captured were
trapped in this maintainer's personal memory and would not flow to
downstream Maestro users.

Resolution: **promote the lessons to a Maestro-shipped Orchestration
Playbook** at `docs/playbook/`. Filed [#73 T1.8](https://github.com/kmeng/maestro/issues/73)
as a new Epic 1 sub-issue specifically for this content half. The
scaffolding-time delivery (auto-copy into user projects + CLAUDE.md
addendum) deferred to a v0.0.4 epic.

### T1.8 (#73) — Orchestration Playbook drafts

Branch `feature/73-orchestration-playbook-drafts`, commit `20f8d2d`, merge
`c54b10a`.
- `docs/playbook/` directory with 6 files (702 lines total): README (index
  + framing + when-to-read pointers), `dispatch-protocols.md`,
  `tests-are-coder-work.md`, `reviewer-context.md`, `tdd-with-workers.md`,
  `common-traps.md`. All user-voice (no internal task IDs, no journal
  references, no commit hashes — verified by grep).
- Decision to orchestrator-write (not coder-dispatch) the playbook itself
  — explicit application of the existing memory `project_writer_worker_gap.md`
  which calls out that prose/methodology docs are an honest exception to
  dogfooding because the 4-role worker fleet doesn't have a writer.
- Personal memory `feedback_coder_file_modification.md` shortened to a
  one-paragraph pointer at the playbook plus a portable summary for use
  in this maintainer's other (non-Maestro) projects.

### T1.7 (#32) — Epic 1 end-to-end verification

Branch `feature/32-epic1-e2e-verification`, commit `34cbde8`, merge `d28bf57`.
- `tests/smoke/epic1_smoke.sh` (196 lines) — 14 automated checks: install
  current; launcher starts in tmp project dir; wizard welcome / step2
  default prefill / inline validate-field Chinese error / step3 confirm /
  save persists; GET /api/team round-trip; GET /team catalog; POST /team/
  edit/<role> updates a row; broken team.yaml → 422 + Chinese invalid
  banner; restore via JSON POST recovers; server killed cleanly + port
  freed.
- `tests/smoke/epic1.md` (139 lines) — markdown checklist mirroring
  `epic0.md`'s style. Three manual scenarios for MCP coder dispatch
  (fallback / valid / refusal paths) that require a real Claude Code
  session.
- Coder dispatch (134s / 7175 tok). Two coder concerns flagged real
  problems: (a) POST /api/team JSON shape (coder guessed flat
  `{role: ...}`, actual is `{schema_version, roles: {...}}`); (b) wizard
  form field naming (coder guessed `{role}_member`, actual is
  `member_{role}`). Both fixed before first run. Plus a launcher-PID
  capture issue: `(cd ... && maestro-webui) &` captures the subshell PID
  not uvicorn's, so kill doesn't release the port. Fixed with
  `(cd ... && exec maestro-webui) &` — exec replaces the subshell, so `$!`
  is uvicorn directly. 14/14 PASS, verified idempotent across two
  successive runs.

### Epic 1 (#13) parent closed + savings refresh

- Closed parent issue with a summary comment listing all 8 sub-tasks,
  the acceptance contract (epic1_smoke.sh + epic1.md), dispatch
  economics, and the major mid-epic adjustments (schema realignment,
  reviewer promotion, T1.8 addition, scribe bug filing).
- `python3 scripts/render_savings.py` re-rendered `docs/savings.md` from
  46 dispatch rows: 23 closed tasks total, 305,731 tokens captured,
  $13.86 saved (98.7%). Commit `2137571`.

## Decided

- **Adopt explicit Realignment PR before T1.1 instead of letting T1.1's
  spec carry stale schema**. The 30-minute upfront cost of changing
  ADR-0004 + design 13 + README + 3 issue bodies was much cheaper than
  the cost of T1.1 + T1.2 + T1.4 + T1.5 + T1.6 each separately
  re-discovering the stale schema, mid-spec.

- **`TeamConfigInvalid` typed wrapper, not raise-and-catch**. The brief
  said "ValidationError (or a typed wrapper)". Going with the wrapper
  keeps `load_team_config`'s contract uniform — three return states, no
  exception leakage — and lets the HTTP API layer's `_format_invalid_detail`
  handler unwrap both YAML-parse-fail and pydantic-fail cases through one
  signature.

- **Reviewer promotion out of shadow happened mid-epic, not at epic
  boundary**. The promotion criterion was "explicit user signal after
  enough side-by-side comparisons." Two side-by-sides (T1.1, T1.2) were
  enough; waiting for an arbitrary count would have been ceremony.
  Conversely, scribe stays in shadow — no user signal yet, no rush.

- **Coder modifications correction is the day's most consequential
  decision**. The first version of `feedback_coder_file_modification.md`
  said orchestrator-handles-modifications-as-default. User correctly
  flagged this as fundamentally wrong: it would have made Maestro a
  "dogfood the greenfield, hand-code the modifications" tool, which is
  not its value proposition. The rewrite locked in coder-by-default with
  full-file-content in spec as the working protocol.

- **T1.8 added during Epic 1 retrospective, not deferred to v0.0.4**.
  When the question "how do other Maestro users get these lessons" came
  up, the easy answer was "later epic". The chosen answer was "now,
  Epic 1 sub-issue, content-half" — based on the realization that
  drafting under (a) the heat of fresh experience and (b) integrated
  with the closing epic is much cheaper than drafting later from
  archived journal entries. The v0.0.4 scaffolding-delivery epic gets
  finished content to work with from day one.

- **Reject reviewer's T1.4 high-severity finding with documented
  rationale**. New protocol invariant: trust reviewer's verdict directly
  except when it's obviously wrong on quick read, in which case
  override AND document the override (PR body / commit message / issue
  comment). The T1.4 reviewer didn't have RoleEntry validator's source
  in its context, so it reasoned correctly from incomplete information.
  Solution going forward (now in playbook): include cross-module
  reference code in reviewer spec.

- **Hardcoded Chinese header on team.yaml (per design 13 D6) even
  though ADR-0004's example shows English**. Spec ambiguity resolved by
  reading both docs and picking the one targeting runtime user surface.
  ADR's English example stays as illustration; runtime artifact is
  Chinese.

## Deferred

- **Common Python traps memory file (`feedback_common_traps.md` etc.)**.
  Considered writing one for the import-by-name monkeypatch + starlette
  TemplateResponse + Pydantic v1/v2 + async test issues. Decided not to:
  these are not Maestro-specific; they're already in
  `docs/playbook/common-traps.md` user-voice. A personal-memory version
  would be a near-duplicate.

- **Scaffolding-time playbook delivery (v0.0.4 epic)**. Not opened as a
  GitHub issue today because v0.0.4 hasn't started. Will file when v0.0.4
  scope is being set. Content is ready (`docs/playbook/`), epic just needs
  the auto-copy + CLAUDE.md-write + maestro install integration code.

- **Coder MCP description 1-line hint addition**. Brief mentioned this as
  an Epic 5 micro-task — adding "for file modifications, include the file's
  full current content in the spec" into the `coder` MCP tool's description
  so any orchestrator (not just Claude Code on this project) sees it at
  tool-discovery time. Not filed today; will file when prioritized.

- **`scripts/render_savings.py` refresh hook**. The
  `feedback_savings_refresh_per_epic.md` memory triggers a manual
  refresh on Epic close. Considered automating via a git hook or
  scheduled task. Decided to keep manual — the hook would add complexity
  for very little gain (refresh is 1 command, runs in <1s, doesn't need
  to be on every commit).

- **Reviewer's false-positive feedback memory**. Considered writing a
  "reviewer's false-positive pattern: it reasons from incomplete
  cross-module context" entry. Decided the playbook entry
  `reviewer-context.md` covers this in the right (user-facing) voice;
  a personal-memory shadow would be redundant.

## Handoff for next session

- **Branch state**: on `v0.0.3`, fully clean, head `2137571`, fully
  pushed to `origin/v0.0.3`. No local feature branches. 242 unit tests
  passing; 14/14 epic1 smoke checks passing (manual portion
  unverified — needs a Claude Code session running against a project to
  confirm the cross-process MCP path).

- **Open issues at session end**:
  - **Closed today (this arc)**: #26 (T1.1), #27 (T1.2), #28 (T1.3),
    #29 (T1.4), #30 (T1.5), #31 (T1.6), #32 (T1.7), #73 (T1.8), #13
    (Epic 1 parent). 9 closes.
  - **Filed today**: #72 (scribe schema bug, Epic 5 / v0.0.4); #73 (T1.8,
    closed same day).
  - **Open**: tracking #2, #3; v0.0.3 epics #11, #14, #15, #16; v0.0.3
    sub-issues across Epics 2, 3 (#33–#51); Epic 7 sub-issues #66–#70;
    governance #17; backlog #72; #18 (sub-issue migration).

- **Next implementation candidates** (v0.0.3 scope remaining):
  1. **Epic 2 (project scaffolding)** — design lands first task at T2.1
     (#33, Pydantic operation taxonomy). Excellent TDD candidate per the
     playbook's `tdd-with-workers.md`.
  2. **Epic 3 (observability)** — T3.1 (#42, Pydantic event models +
     truncation utility) likewise.
  3. **Epic 7 (Web UI savings page)** — T7.1 (#66, extract calc core).
     Smaller, faster epic. Can interleave with 2 / 3.

- **Mandatory reading before any T2.x work**: design 14
  (`docs/design/14-epic2-project-scaffolding.md`), ADR-0005 (scaffolding
  template set), ADR-0006 (take-over merge mechanics), parent epic #14.

- **Watchpoints carried forward**:
  - Latent async-dispatch timeout (no `asyncio.wait_for` on background
    job runner) — still not addressed. Today's parallel dispatches
    didn't expose it.
  - Scribe stays in shadow mode; will hit it on the first scribe
    dispatch that's worth side-by-side evaluation.
  - **New**: `docs/playbook/` content lives in the repo now — future
    PRs that surface new playbook-grade lessons should append to the
    relevant entry (or open a new one), not leave them in personal
    memory.
  - **New**: starlette `TemplateResponse(request, name, context)` API
    bites recurrently. Worth pre-empting in every webui spec going
    forward.

- **Article + Obsidian** for this arc is in flight at session end —
  same pattern as the past three arcs.

## Process learnings

- **A pre-implementation realignment PR can be the cheapest task of an
  epic**. The 30-minute schema realignment commit (ADR-0004 + design 13
  + README + 3 issue bodies) unblocked all 6 implementation tasks
  downstream. Each task would have hit the stale-schema problem
  separately if I'd skipped the realignment; the cumulative re-discovery
  cost would have been hours, not minutes. **When you find a doc that
  the code is about to contradict, fix the doc before writing the code.**

- **Reviewer accuracy is a context problem, not a model problem**. The
  T1.4 reviewer false-positive (claimed a strip wasn't happening) was
  reasonable given what it could see (one file). It became inaccurate
  only because what it needed (RoleEntry's validator from T1.1's
  module) wasn't in the spec. Once you internalize this, the
  improvement path is obvious: pass more context, don't switch models.
  Going forward this is encoded in `docs/playbook/reviewer-context.md`
  and applied protocol: tests-run-first, results-in-spec.

- **The "I'll just fix this small bug myself" trap is the largest
  dogfooding leak.** Watched myself do it three times today (T1.4's
  TeamConfig dict-access bug, T1.4's monkeypatch trap, T1.5's
  TemplateResponse) before user explicitly called it out. Each time
  felt cheap individually. Cumulatively they were the day's largest
  Opus token sink that wasn't strictly necessary. **The correction:
  re-dispatch coder with sharper spec; the orchestrator's role is
  enumeration + verification + landing, not surgical impl.** This is
  the single most consequential discipline correction of the day.

- **Memory promotion ladder: personal → project docs → shipped product**.
  Lessons start as personal `feedback_*.md` memory entries. When a
  lesson stops being maintainer-specific, it deserves to climb the
  ladder. Today that happened explicitly for the first time — five
  Epic 1 lessons got promoted from personal memory into
  `docs/playbook/` user-voice entries that will ship to Maestro users.
  **The rule that surfaced: every personal-memory entry should be
  periodically audited — would another user of this project benefit
  from this? If yes, it doesn't belong only in personal memory.**

- **Parallel coder dispatches work; parallel branch landing should
  remain serial**. Two coders ran in parallel three times today (T1.3
  + T1.6, T1.4 + T1.5, plus T1.7 + the playbook orchestrator-side
  draft). Each time, dispatch was max(wall_a, wall_b) not sum. Landing
  was serial without conflicts because the two branches touched
  different files. **The pattern: dispatch is parallel; landing is
  serial; the gap between them is where the orchestrator does its
  judgment work, and that judgment work is fast.**

- **Coder concerns are a real channel — listen to them.** Three times
  today the coder's concerns section called out exactly what later
  turned out to be the bug. T1.2's "inferred file contents — verify
  against actual repo" was correct (the inferred __init__.py would
  have dropped exports). T1.4's "version placeholder is hardcoded" was
  the right concern. T1.7's "JSON shape and form field naming inferred"
  flagged both real bugs. **When concerns mention inferred / assumed /
  guessed, treat the relevant artifact as suspect — don't merge
  without diffing.** This is now in `docs/playbook/dispatch-protocols.md`.

- **An epic-closing E2E smoke script is a paying-forward asset.** T0.7's
  `epic0_smoke.sh` paid interest to today's work — when Web UI internals
  shifted under T1.4 / T1.5, running the Epic 0 smoke confirmed the
  hero page + /health + port-conflict still worked. T1.7's
  `epic1_smoke.sh` does the same for any future PR that touches Epic 1
  surface. **Every "E2E verification" task isn't a closing formality;
  it's a regression gate for every later epic.** Worth doing them
  carefully, not as a checkbox.

- **The "should this be coder or orchestrator" question has a clear
  answer for code, and a clear answer for prose, and a fuzzy answer for
  the middle**. Today's middle case was the orchestration playbook
  itself. The decision (orchestrator-write) leaned on an explicit
  pre-existing memory (`project_writer_worker_gap.md` — "no writer in
  the 4-role fleet; prose is orchestrator's exception"). **The discipline
  is: have a default (coder), have a documented exception (writer-gap),
  and check which side you're on rather than defaulting to convenience.**

- **One day, one Epic.** Epic 0 in 5 sessions of yesterday; Epic 1 in
  one day today. Epic 0's pace was set by the foundational work
  (pyproject.toml, launcher, paths.py). Epic 1's faster pace was the
  payoff — most T1.x tasks were "compose what Epic 0 set up with new
  business logic", not "establish new infrastructure". **Epics that
  follow foundational ones go faster, sometimes by 5x. Plan release
  schedules with that asymmetry in mind.**
