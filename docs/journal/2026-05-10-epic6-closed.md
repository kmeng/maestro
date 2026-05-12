# 2026-05-10 — Epic 6 Closed

> Third arc of the day. Sibling to `2026-05-10.md` (morning + afternoon
> arcs). Kept separate because this evening has its own narrative
> centre: the sprint that took Epic 6 from 4/8 to 8/8 in one continuous
> session, plus the four nested design surfacings the sprint exposed.

## Session 3 — evening (CST)

The afternoon's scope-split for Epic 6 left four open sub-tasks (T6.4
methodology, T6.5 backfill, T6.6 README link, T6.8 retire begin_task.sh).
The evening picked them off in sequence T6.8 → T6.4 → T6.5 → T6.6,
plus the epic close. Five closed loops. Three new memories from
discoveries inside the work. Two ADRs (0010 + 0011). One renderer
feature added inline because a backfill design need surfaced it. Net:
Epic 6 100%, project's "10–20% the cost" claim now backed by
mechanical evidence updating per dispatch.

## Done

- **T6.8 (#64) — retire begin_task.sh; dispatch attribution via
  parameters with branch fallback**. Two-commit branch
  `feature/64-retire-begin-task` (`6bbde3a` design + ADR-0011;
  `d127ead` impl + tests + doc updates). The `_resolve_attribution`
  precedence chain (explicit param > env var deprecated > git branch
  > unattributed) replaces the env-var-only path. Four worker schemas
  gain optional `task_id` + `issue_number` (scribe reuses its
  required `issue_number` field — flagged that scribe's required
  workflow-coupled fields are themselves a separate problem; memory
  `project_pure_worker_schemas.md`). 9 new tests in
  `test_dispatch_telemetry.py` covering 4 precedence layers + warning
  one-shot + regex unit + scribe reuse + partial-param no-backfill.
  `tests/conftest.py` updated to neutralise git subprocess by default
  so tests don't drift based on dev branch state. **Coder dispatch:
  deepseek-v4-pro, 193.28s, 10,530 tokens (banner-captured)** —
  attributed via this same task's branch fallback once T6.8 went
  live (recorded as a supersede row in T6.5). One worker miss caught
  at integration: existing `test_emit_records_null_task_when_env_unset`
  failed because the dev branch (`feature/64-...`) triggered the new
  branch fallback; the conftest fix was the ~2-line resolution.
  CLAUDE.md updated to mandate dispatching with task_id/issue_number.
  All 122 tests green after merge.

- **T6.4 (#61) — `docs/savings-methodology.md` + ADR-0010**. Two-commit
  branch `feature/61-savings-methodology` (`8237b8c` `chore(gitignore)`;
  `5a196c8` `docs(methodology)`). Hand-written orchestrator-only work
  — the 4-role fleet has no fit for creative technical doc creation;
  surfaced as deliberate exception, not silent fallback (memory
  `project_writer_worker_gap.md`). 8 sections per design 56 §5:
  measured / estimated / Opus formula / provider rates with sources +
  snapshot date 2026-05-10 / gaps not-measured / reproducibility /
  disable mechanism / honesty key (✓ ⚠ ◇ —). ADR-0010 consolidates 3
  decisions: append-only JSONL, same-token Opus baseline as lower
  bound, provider rates baked into renderer code. **Pre-write, a latent
  design contradiction surfaced**: design 56 §7 said "committed audit
  trail" but `.gitignore`'s `*.jsonl` pattern was actively excluding
  the file. Resolved with a `!docs/data/dispatch-log.jsonl` carve-out
  in the same task; reproducibility claim in §6 of methodology page
  now actually holds (`git checkout <hash> && python
  scripts/render_savings.py && diff` is empty by design).

- **T6.5 (#62) — backfill historical + 5 attribution fixups + renderer
  supersedes**. Two-commit branch `feature/62-backfill` (`878e59f`
  `feat(renderer)`; `124a6f8` `docs(savings)`). Scope expanded twice
  per user decisions during analyze phase: (a) include T6.1/T6.2/T6.3
  alongside the originally listed 6 historical tasks (same data
  shape, same gap); (d) add 5 supersede rows to fix attribution on
  unattributed live emits (T6.7 librarian, T6.8 coder, T6.5's own 3
  librarian extractions). The (d) decision exposed that the renderer
  didn't yet implement the schema's `supersedes` field — addressed
  with `filter_superseded` (~30 LOC + 3 unit tests) in the first
  commit. **Dogfooded by dispatching 3 librarians in parallel** to
  extract dispatch metadata from old journals; my prompt asked for a
  free-form JSON array which violates librarian's
  `{hard_constraints, summary, ...}` dict contract — all 3 returned
  `output_schema_invalid` BUT the `raw` field preserved the data, so
  it was usable. 20 backfill rows + 5 supersede rows appended to
  `docs/data/dispatch-log.jsonl` via a one-shot helper script
  (`/tmp/backfill_t6.5.py`, kept ephemeral — design choice, not
  commit-worthy). Re-rendered `docs/savings.md`: **12 closed tasks /
  25 dispatches / $6.40 saved (98.9%)**. Determinism verified
  byte-identical on re-run. T0.1 + T5.1 render as `rate-unknown ⚠`
  because they used legacy `deepseek-coder` (not in `PROVIDER_RATES`)
  — design-correct per methodology §4, not a regression.

- **T6.6 (#60) — README link to `docs/savings.md`**. Single-commit
  branch `feature/60-readme-savings-link` (`8a85ffe`). +2 lines
  blockquote callout placed at README:9, immediately after the
  "**10–20% the cost**" claim sentence. The link's natural home —
  evidence next to claim, no scroll. H3-protected doc edit, T6.6 is
  the dedicated issue per governance rule. Diff +2 well under the
  5-line cap.

- **Epic 6 (#56) closed at 8/8 (100%)**. Final close-comment
  (`comment-4414607375`) summarises shipped artifacts (savings.md,
  methodology.md, dispatch-log.jsonl, ADRs 0010 + 0011, README link),
  the 8 sub-issues by ID, baked-in decisions D1/D2/D4/D6/D10 and
  superseded D7, worker-quality observations, three deferred next
  horizons (Epic 7, worker schema purity, writer role gap), and the
  three-arc story of how the day landed.

## Decided

- **Audit-trail data files are part of the project, not transient
  runtime noise**. User's framing during T6.4 prep: "gitignore is for
  files temporarily produced during project runs; dispatch-log.jsonl
  is part of my project, can be committed." Carved
  `!docs/data/dispatch-log.jsonl` exception out of the broad
  `*.jsonl` ignore. The principle generalises — ask of every
  candidate-for-ignore file: "is this byproduct or product?" The
  reproducibility claim in methodology §6 only holds because the
  data side of the contract is committed.

- **`supersedes` field works precisely because it preserves the
  original**. The append-only JSONL design (D4, ADR-0010) and the
  need to fix historical attribution looked like opposites. They
  aren't: a row with `supersedes: <id>` is a NEW row that REPLACES
  the original in aggregation but doesn't delete it from the file.
  History stays whole; the rendered view stays clean. Required ~30
  LOC in the renderer (`filter_superseded`); the schema field has
  existed since T6.2 design but was decorative until T6.5 needed it.
  General lesson: fields you put in a schema "in case we need them"
  often go decorative for months — wire them up the first time you
  actually need them, not at design time.

- **Scope expansion is honest scope expansion when it shares the
  same gap**. T6.5 was specified for 5/6 historical tasks. During
  analyze phase the same data shape (measured banner data in journal,
  not in JSONL because of pre-restart MCP) showed up for T6.1 / T6.2
  / T6.3 too. Surfaced as decision (a) → user approved expansion.
  Including them cost ~3 extra rows; excluding them would have
  produced an incomplete page that obviously hid today's Epic 6 work.

- **Worker quality issue captured rather than papered over**:
  librarian's strict-dict contract (`{hard_constraints, summary,
  recommend_full_read, concerns, _banner}`) means asking it to return
  a free-form JSON array fails schema validation. T6.5 hit this 3×
  but recovered usable data from the `raw` error field. Captured as
  worker-quality observation in Epic 6 close-comment + journal here;
  worth a future librarian-prompt-template improvement that
  documents this constraint explicitly to prompt-writers.

- **Writer worker gap is exception-by-necessity, not fallback**.
  T6.4 was orchestrator-written despite the dogfooding rule because
  no worker fits creative technical doc creation (coder = code,
  librarian = extract, reviewer = code review, scribe = commit
  messages). Documented in `project_writer_worker_gap.md`. Surface +
  proceed > silent skip. Possible v0.0.4 role expansion.

## Deferred

- **Latent async-dispatch timeout bug** (carried from morning) — still
  no `asyncio.wait_for` wrapping the API call. Today's longest
  dispatch was T6.8 coder at 193s (T6.5 librarian also hit 70s); none
  hung but the watchpoint stands.

- **Epic 7 (general-user savings UX in Web UI)** — design session
  pending; memo at `project_epic7_general_user_savings.md`. The two
  schema-purity items (`project_pure_worker_schemas.md` for scribe;
  also potentially `librarian` returning richer free-form output) may
  fold under Epic 7 or get a sibling epic.

- **`deepseek-coder` rates in `PROVIDER_RATES`** — T0.1 + T5.1 render
  as `rate-unknown ⚠`. Adding the historical pricing would normalise
  these rows; needs verified historical pricing values. Not blocking.

- **CI enforcement of renderer determinism** (D9 in #56) — manual
  check via `diff <(git show HEAD:docs/savings.md) docs/savings.md`
  works today; v0.0.4 should automate.

## Handoff for next session

- **Branch state**: on local `v0.0.3`, fully pushed to `origin/v0.0.3`
  through merge `4c85fb2` (T6.6). All 4 evening feature branches
  (`feature/64-retire-begin-task`, `feature/61-savings-methodology`,
  `feature/62-backfill`, `feature/60-readme-savings-link`) merged
  locally — safe to delete locally for clean `git branch` output;
  no remote presence.

- **Open issues at session end**: tracking (#2, #3); v0.0.3 epics
  (#11–#16, #52); v0.0.3 sub-issues (#22–#51, plus T6.x already
  closed today). **Closed today (cumulative across all 3 arcs)**:
  #21 (T0.3), #57 (T6.1), #58 (T6.2), #59 (T6.3), #63 (T6.7),
  #64 (T6.8), #61 (T6.4), #62 (T6.5), #60 (T6.6), and **#56 (Epic 6
  itself)**.

- **MCP server is still running pre-T6.8 code** — every dispatch
  this session was unattributed at emit time and got attribution-
  fixed via T6.5 supersedes after the fact. **Next session should
  open with a Claude Code restart** so the MCP picks up the T6.8
  parameter handling + branch fallback + deprecation warning. Then
  any dispatch carries `task_id` / `issue_number` per the new
  CLAUDE.md mandate; no more retroactive supersede rows needed.

- **Next implementation candidates** (Epic 6 done; back to Epic 0/1/2/3):
  1. **T0.4 (#22)** — empty-shell Web UI page + vendored htmx.
     Resumes Epic 0 forward progress. First task to exercise T6.8's
     parameter attribution end-to-end (orchestrator passes
     `task_id="T0.4"`, `issue_number=22` on every worker call).
  2. **T1.1 (#26)** — Pydantic team config models + DEFAULT_MODELS.
     Already partially blessed by Session 1 librarian validation.
  3. **Epic 7 design session** — separate session per memo.
  4. **Wiki article repost** — the "First Fleet Run" milestone
     article from 2026-05-09 can now claim measured savings,
     replacing the estimate. Link target = the now-rich savings.md.

- **Mental thread**: this evening was a sprint, not a forced march.
  Each task's design surfacing (gitignore mistake, supersedes-
  doesn't-exist, librarian-schema-fails, writer-role-gap) became a
  tracked finding rather than a workaround. The cost: ~30 minutes
  of extra session time across the four. The benefit: each finding
  exists as a memory or commit, not as silent debt for future-Opus
  to rediscover. **Memory hygiene during sprints is what makes
  sprints sustainable**.

- **Watchpoints carried forward**:
  - Timeout bug (still unfixed)
  - Librarian's strict-dict contract is poorly documented to
    prompt-writers (today's 3 dispatches all violated it)
  - Renderer determinism needs CI gate (manual today)
  - Scribe / librarian schema purity (Epic 7 likely scope)
  - 11 commits pushed to `v0.0.3` today (4 feature merges +
    journal merges + chore commits) — when v0.0.3 ships,
    release-PR commit listing will be substantial; probably
    benefits from a BUILD_LOG entry summarising

## Process learnings

- **Surfacing a latent contradiction is the methodology page's job
  before its content's job**. T6.4's first prep step found that
  `*.jsonl` in `.gitignore` contradicted design 56 §7's "committed
  audit trail" — a contradiction that, if unfixed, would have made
  methodology §6's reproducibility claim a lie. Discovering this
  while prepping the page (rather than after publishing it) cost 5
  minutes; discovering it after publication and quietly retracting
  would have been a credibility hit. **Writing transparency
  documentation is a verification pass, not a recording pass**.

- **Schema fields put in "in case we need them" go decorative
  until the first user**. `supersedes` was in the JSONL schema since
  T6.2 design (~24 hours ago). It looked decorative because nothing
  consumed it — until T6.5 needed to fix attribution and discovered
  the renderer ignored it. Fixed inline in T6.5's branch (~30 LOC).
  General rule: don't add schema fields aspirationally; add them at
  the first concrete use, with the consumer code in the same PR.
  When you DO add aspirationally, write a TODO that future-anyone
  will see and either implement or remove.

- **"Same data shape, same gap" is the right test for in-scope
  expansion**. T6.5 was scoped to 5/6 historical tasks. T6.1/T6.2/T6.3
  had the same shape (measured banner data not in JSONL because of
  pre-restart MCP) and same backfill mechanics. Expansion from 6 to
  9 tasks added marginal effort but completed the page. The wrong
  expansions are "while I'm here, let me also rewrite the renderer
  for X" (different shape, different gap). The right ones are
  "while I'm here, the next 3 things have identical shape — bundling
  is cleaner than 3 follow-up issues each repeating the same setup."

- **Dogfooding partial-failure is recoverable when the worker emits
  raw output**. 3 librarian dispatches today violated librarian's
  dict contract because my prompt asked for a JSON array; all 3
  returned `output_schema_invalid` BUT the `raw` field preserved the
  data. Recovery: read the raw, treat as truth. Lesson: server-side
  output validators that include the raw output in the error
  response (rather than just dropping it) preserve recoverability.
  Worth checking if all 4 worker validators do this — if not, fix
  before next sprint.

- **Worker-fit honesty beats dogfooding compliance**. T6.4 was
  orchestrator-written because no worker fits creative technical doc
  creation. A weaker orchestrator would have invented a librarian or
  scribe dispatch to "satisfy the rule" — producing thin output and
  a fake checkmark. The dogfooding memory's actual rule is "must
  dispatch when feasible; surface when not." Surfacing today produced
  a memory entry (`project_writer_worker_gap.md`) that becomes input
  to v0.0.4 role expansion. The non-dispatch is *more* aligned with
  dogfooding than a forced dispatch would be.

- **One sprint, four "discoveries inside the work"**. T6.8 surfaced
  scribe's workflow-coupled `issue_number` (memory'd). T6.4 surfaced
  the gitignore vs design contradiction (fixed). T6.5 surfaced the
  renderer's missing `supersedes` (added). T6.5 also surfaced the
  librarian-strict-dict gotcha (memory'd). None of these were on the
  task briefings — they were the cost of actually doing the work.
  **The cost of "doing the work" is finding what the briefing
  didn't say**. Plan briefings to leave room for ~1 surfacing per
  closed loop; that's typical. If a sprint produces 0 surfacings,
  the briefings were too detailed (no slack); if it produces 5+,
  the briefings were too thin.

- **Memories written DURING the work, not after, become next
  session's inputs**. Today wrote 3 new project memories
  (`project_epic7_general_user_savings`,
  `project_pure_worker_schemas`, `project_writer_worker_gap`) and
  1 feedback memory (`feedback_distinguish_user_from_general`) at
  the moment of surfacing — not at end-of-day. Each shows up at next
  session's MCP boot. The temptation is "let me batch all memories
  for end-of-session"; the right move is "write the memory at the
  surfacing moment, then continue the work." Batching loses the
  precise framing that makes the memory useful months later.

- **Closed-loop discipline survives evening fatigue when the loops
  are short**. T6.8 took ~90 min (most code-heavy of the four).
  T6.4 ~60 min. T6.5 ~75 min (would have been longer without the
  3-parallel librarian dispatch saving journal-reading time). T6.6
  ~10 min. None individually long enough for fatigue to compound;
  each ended with `main` green + tests green + issue closed. The
  evening's productivity wasn't heroism — it was task-shape:
  no task larger than what fits in working memory.
