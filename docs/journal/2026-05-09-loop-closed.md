# 2026-05-09 — The Loop Closed

> Standalone session entry. Sibling to `2026-05-09.md` (Sessions 1 + 2 of
> the same day). Kept separate because this session has its own narrative
> centre: the first end-to-end dispatch fleet run plus the celebratory
> artifacts that came with it.

## Session 3 — afternoon (CST)

The day's three-session arc lands: Sessions 1 + 2 built and validated
the Epic 5 fleet (librarian + coder + reviewer + scribe) and fixed the
infrastructure (async dispatch, ADR-0009) that made dispatching real
specs possible. Session 3 took the next implementation task off the
shelf — T0.2 — and ran the entire fleet against it, end-to-end, on its
first turn. The dogfooding loop closes here.

**Done**

- **T0.2 (#20) — extend `.env` loader to `~/.maestro/credentials.env`**.
  Closed loop with full fleet exercise:
  - Branch `feature/20-env-loader-credentials` → `--no-ff` merged into
    `v0.0.3` (`5605fc7` / `dc39235`); BUILD_LOG entry merged after
    (`c4c4532` / `f12b350`).
  - 89-line `maestro/env_loader.py` (set-if-absent semantics; never
    overwrites `os.environ`; project `.env` first then user file so load
    order = precedence; missing-file = silent DEBUG log only).
  - 145-line `tests/test_env_loader.py` — 10 tests covering all 5
    acceptance criteria + parsing edge cases. Full suite 78 pass
    (10 env_loader + 10 paths + 58 workers).
  - `bootstrap/maestro_server.py` integration: inline `_load_dotenv`
    replaced by `from maestro.env_loader import load_credentials;
    load_credentials(project_root=_PROJECT_ROOT)`. Missing-key error
    message updated to list all three precedence tiers explicitly.
  - Bidirectional smoke verified: project-`.env`-only resolution matches
    v0.0.2 byte-for-byte; isolated user-file fallback (HOME=temp, no
    project `.env`) resolves DEEPSEEK_API_KEY end-to-end.
  - Issue #20 closed with a completion comment summarising the dispatch
    pattern + test counts.

- **First end-to-end dispatch fleet run**. Every Epic 5 role earned its
  keep on T0.2's first turn:
  - **librarian × 2** in parallel against design 12 + ADR-0003. Both
    docs stayed entirely outside Opus's context window. Hard constraints
    returned as semantic-verbatim quotes; `concerns` channel surfaced
    one ambiguity in ADR-0003 about missing-file handling, which the
    plan addressed explicitly.
  - **coder × 1** on a tight spec with per-AC mapping. 116.51s wall,
    6066 tokens, deepseek-v4-pro. One concern accepted ("file empty vs
    file missing should be distinguishable in the DEBUG log") — folded
    in at integration time.
  - **reviewer × 1 (shadow)** on integrated `env_loader.py`. Verdict
    `pass`, `findings: []`, `missed_requirements: []`, `concerns: []`.
    Orchestrator's parallel shadow review produced the same verdict
    with three non-blocking observations (`setdefault` simplification,
    `__future__` redundancy, why-comment value retention). User
    explicitly noted shadow comparison was useful and is staying in
    observation mode.
  - **scribe × 1 (shadow)** drafted Conventional-Commits message + PR
    body with co-authorship + `Closes #20`. Orchestrator shadow added
    extra "why" density (mechanism + architecture rationale + test
    counts). User picked worker version verbatim with reasoning:
    "commit message has no real issues; mechanism/architecture rationale
    is recoverable elsewhere, concise is fine."

- **Milestone artifacts published** (3 GitHub-visible places + 1 local):
  - **#52 comment with 5 badges** (milestone, roles active, dispatches,
    tokens saved, date) — [comment-4412069731](https://github.com/kmeng/maestro/issues/52#issuecomment-4412069731).
    Marks Epic 5 as having delivered its product value, not just its
    code.
  - **BUILD_LOG.md v0.0.3 section opened** with T0.2 milestone entry
    (full breakdown of dispatches, savings table, AI contributors
    list) plus a "pending backfill" note for T0.1 + Epic 5 work that
    shipped before BUILD_LOG was being kept current. Merged into
    `v0.0.3` via `docs/build-log-t02-milestone` temp branch.
  - **Wiki bilingual milestone article** at
    `Milestone-2026-05-09-First-Fleet-Run` — EN + 中, identical
    structure both languages, badges header. Home page updated with
    Milestones index and "See also" links to README / governance /
    architecture / BUILD_LOG. Designed for repost to other platforms
    (dev.to / 知乎 / Mastodon / HN); all repo links use absolute
    `https://github.com/kmeng/maestro/...` URLs so they survive
    transplant.
  - **Memory: `feedback_dispatch_telemetry.md`** — from T0.3 onward,
    every dispatch's `[<tool> dispatch — <model> — Xs — N tokens]`
    banner is captured into the session journal as a per-call row.
    By v0.0.3 ship, ~30 real data points replace today's estimate.

**Decided**

- **The dispatch fleet is now the default for implementation tasks**,
  not an experiment. Previously this was a goal articulated in
  `feedback_dogfooding_implementation.md`; today it's the observed
  behaviour on a real task. The next 30 v0.0.3 implementation tasks
  inherit this expectation by default.

- **Branch workflow reminder applied**: temp branches (`feature/...`,
  `docs/...`) merge into local `v0.0.3` first, then only `v0.0.3` gets
  pushed. No PR. No remote feature branches. Issue closed via explicit
  `gh issue close <n>` after merge — `Closes #N` doesn't auto-fire
  when PR base is a non-default branch. The user caught my drift
  toward the standard PR-creation flow mid-stride and corrected it
  before any remote pollution. Convention restored: T0.2 was closed
  via `gh issue close 20` with a completion comment, no PR opened.

- **Token savings stay an estimate today, become a regression from
  T0.3**. ~56% on T0.2 is honest within its assumptions, but
  librarian's banner doesn't carry token counts and Opus's real input
  is reduced by prompt caching. Direct measurement starting next task
  resolves both. Captured in memory; this is now project DNA, not just
  a one-off.

- **Documentation as celebration is also legitimate**. The user framed
  the milestone push ("badges, bilingual article, post-able to other
  platforms") not as polish but as the right amount of attention for a
  rare event. Reinforces the standing project principle that
  documentation is throughput multiplier rather than overhead — and
  extends it to milestone artifacts. Future similar moments (e.g.
  Epic 0 / 1 / 2 / 3 completions; v0.0.3 ship) earn the same
  treatment.

**Deferred**

- **BUILD_LOG.md backfill for earlier v0.0.3 work** — T0.1 + the four
  Epic 5 entries (#52 / #53 / #54 / #55) shipped before BUILD_LOG was
  being maintained for v0.0.3. Today's milestone entry includes a
  "pending backfill" note. Could be its own small docs task; not
  blocking next implementation work.
- **Reposting the wiki article to external platforms** is now the
  user's call (timing, which platforms, any framing tweaks for each
  audience). The article itself is publish-ready as-is.
- **Promotion of reviewer / scribe out of shadow mode** — still
  awaiting user signal. Today's run gave one strong data point
  (worker reviewer matched orchestrator shadow verdict; worker scribe
  was selected verbatim by the user). Need a few more before the user
  is positioned to promote.

**Handoff for next session**

- **Branch state**: on local `v0.0.3`, fully pushed to `origin/v0.0.3`.
  Working tree clean. Local branches retained: `feature/20-env-loader-credentials`,
  `docs/build-log-t02-milestone` (both already merged; safe to delete
  locally if you want clean `git branch` output, but no remote
  presence either way).
- **Open issues at session end**: tracking (#2, #3); v0.0.3 epics
  (#11–#16, #52); v0.0.3 sub-issues (#21–#51). **Closed today
  (cumulative across all 3 sessions)**: #19 (T0.1), #53 (T5.1),
  #54 (T5.2), #55 (T5.3), #20 (T0.2). Epic 5 fully shipped; first
  Epic 0 task closed.
- **Next implementation candidates** (pick one):
  1. **T0.3 (#21)** — FastAPI app skeleton + `/health` and `/version`.
     Larger than T0.2 but well-bounded; first introduction of the
     Web UI surface. **First task to execute under the
     telemetry-from-T0.3 rule** — every dispatch banner gets recorded
     into this session's journal as a per-call row.
  2. **T1.1 (#26)** — Pydantic team config models + DEFAULT_MODELS.
     Already partially blessed (librarian validation in Session 1
     covered T1.1's hard constraints). Worker dispatchable end-to-end.
- **Mental thread for next session**: telemetry recording starts on
  the very first dispatch. Format: append to the journal entry's
  "Dispatches" section a markdown table with `task | tool | model |
  wall_s | tokens` per row. By v0.0.3 ship, ~30 rows produce a
  measured savings ratio that supersedes today's estimate.
- **Watchpoints carried forward**:
  - **Role-fleet usability across real work** — top-priority watchpoint
    from yesterday's journal still applies. T0.2 was one data point
    (clean run, no degradations). Need 4–5 more across diverse task
    shapes (HTTP API, UI, data validation, complex refactor) before
    we can call the fleet "stable on real work."
  - **librarian token reporting** — banner currently doesn't include
    tokens. Either fix the banner to report, or document the gap and
    estimate by document size. Will surface as a parse miss in the
    T0.3 telemetry table.
  - **OPEN-5.7** (librarian hit rate) — effectively resolved by
    semantic-verbatim recalibration. Still worth observing across
    more tasks.
  - **OPEN-5.1** (oversize documents > 80K chars) — handler refuses;
    revisit on first observed refusal.
  - **bootstrap `sys.path` shim** (T0.1) is still transitional;
    T0.5 replaces it with `pyproject.toml` packaging.

**Process learnings**

- **End-to-end on the first turn beats end-to-end on the third try**.
  T0.2 was the first task after Epic 5 + ADR-0009 closed, and it
  exercised every role on its first turn — no warm-up, no "let me
  use the new tool deliberately." When a tool has been built right,
  the orchestrator reaches for it by reflex, not by ceremony. That
  reflex is the test of whether the tool is actually finished. The
  fleet passed.

- **Branch-workflow correction caught early is a process win, not a
  failure**. Mid-execution I drifted toward `gh pr create` because
  it's the default reflex from generic GitHub workflows. The user's
  one-line correction redirected to local-merge → push v0.0.3 → close
  via `gh issue close`. The cost of the correction was seconds; the
  cost of pushing a feature branch + opening a PR + then having to
  delete it would have been much larger. **Asking before
  state-changing remote actions is what made the correction possible.**
  This is the value of the `feedback_github_approval.md` rule —
  observed in the wild today.

- **Estimates are necessary, but they expire on first measurement**.
  Today's "~56% saved" was the right answer at the time (no
  telemetry yet) but stale within hours of being written —
  measurement starts next task. The honest claim becomes a measured
  one before any external audience reads it on Monday. This is the
  pattern: ship the estimate with explicit ⚠️ + commitment to
  measure; replace the estimate as data arrives. Don't wait for
  perfect data to make a claim, but don't pretend a claim is more
  than it is.

- **Celebration is part of the engineering, not a distraction from
  it**. The wiki article + BUILC_LOG entry + #52 comment took
  ~20 minutes of orchestrator time and produced four artifacts that
  will be referenced internally for the rest of v0.0.3 (and
  externally if reposted). The cost of celebrating a real milestone
  is bounded; the cost of skipping celebration is invisible but
  substantial — future contributors and future-Opus lose the
  narrative anchor that says "this was the hinge point." Today
  earned it. Future hinges (epic completions, version ships) earn
  the same.

- **Three sessions per day was high-throughput, not chaos**. Sessions
  1 + 2 (yesterday's journal) ran ~12 hours; Session 3 ran ~3 hours.
  The rhythm worked: Session 1 found the cost problem and built the
  role solution (Epic 5 design + T5.1 phase 1+2), Session 2 closed
  Epic 5 (T5.2 + T5.3 + ADR-0009) and validated the fleet end-to-end
  via MCP path, Session 3 used the fleet on a real task and
  celebrated. Each session had a coherent goal even though they
  weren't planned as a sequence. Worth noting: the user's
  willingness to keep going past Session 1's premature journal was
  what made the day's full arc possible. Premature stopping would
  have left Epic 5 half-shipped with a cost analysis but no closed
  loop.
