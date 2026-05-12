# 2026-05-10 — Epic 7 Design

> Fourth arc of the day. Sibling to `2026-05-10.md` (morning + afternoon)
> and `2026-05-10-epic6-closed.md` (evening). Kept separate because
> this late-evening arc is a single-purpose design session: Epic 7 lifted
> from a memo to an approved design + 5 sub-issues, no implementation
> yet. The artifact set is small (1 design doc, 1 epic body, 5 sub-issue
> bodies, 3 memory updates) but the decisions baked in are the reason
> the next implementation session can start cold without re-deriving
> them.

## Session 4 — late evening (CST)

The previous arc closed Epic 6 8/8 and left Epic 7 as the next
candidate "design session" per the handoff. This session executed
exactly that: opened the epic, wrote the design doc, revised it once
mid-review (per-task removal), filed 5 sub-issues, and updated three
memories so the design state survives the session boundary. No code
written. The point of the session was to make the next session's code
cheaper, not to start it.

## Done

- **Epic 7 ([#65](https://github.com/kmeng/maestro/issues/65)) opened**
  — title `Epic 7: Web UI savings page — general-user view of own
  dispatch costs`. Body explicitly enumerates "Why a separate epic
  from Epic 6" (the framing decision from the morning arc), in-scope,
  out-of-scope, and the Epic 0 dependency. Body went through one
  revision after the per-task scope change (see below). Final body
  written via `--body-file` after an inline-heredoc gotcha (process
  learnings §).

- **Design doc [docs/design/65-web-ui-savings-page.md](docs/design/65-web-ui-savings-page.md)
  written**. 10 sections, ~280 lines. Mandatory `feedback_distinguish_user_from_general.md`
  treatment lives in §1 — explicit "For maestro the project (dogfooding)"
  vs "For general users" sub-sections, listing what is foregrounded for
  each audience. The two views share a calc layer (§3.1) but differ in
  what they render. Design also covers: route + page structure (§2),
  empty/disabled/error states (§2.3), no-live-refresh decision (§2.4),
  Web UI route sketch (§3.2), templates (§3.3), no-caching rationale
  (§3.4), test surface (§3.5), failure-mode matrix (§4), affected
  modules (§5), dependencies (§6), 5 sub-task preview (§7), explicit
  out-of-scope recap (§8), 2 open questions (§9), no-ADR rationale
  (§10).

- **Per-task scope removed mid-review**. First draft included per-task
  as a conditional fourth table (renders only when at least one row
  carries `task_id`). User's "2.2.4 拿掉，不需要" prompted a full
  cross-section sweep. Edits landed across §1.1, §1.2, §2.2, §2.3,
  §3.2, §3.5, §4, §6, §7, §9 to remove every per-task reference and
  re-justify the cleaner shape. The calc layer still exports
  `group_by_task` because the Markdown renderer needs it — only the
  Web UI surface drops per-task. Justification: general users may
  never adopt `task_id`; per-task users already have
  `docs/savings.md` from Epic 6. Splitting the surface for a feature
  general users don't need was complexity without value.

- **5 sub-issues filed under #65 via native sub-issue API**. Used the
  existing `scripts/create_subissue.py` helper (from issue #17
  governance amendment work) — takes parent issue + title + body file,
  does both `gh issue create` and the sub-issue link POST. Created
  sequentially to keep issue numbers in order:
  - [#66 T7.1](https://github.com/kmeng/maestro/issues/66) — extract
    calc core from `render_savings.py` to `bootstrap/savings.py`.
    Determinism gate: re-rendered `docs/savings.md` byte-identical.
    Unblocked today.
  - [#67 T7.2](https://github.com/kmeng/maestro/issues/67) — add
    `group_by_time(rows, "day")` + `resolve_log_path()` to
    `bootstrap/savings.py`. Unblocked today (after T7.1).
  - [#68 T7.3](https://github.com/kmeng/maestro/issues/68) — Web UI
    route `GET /savings` + happy-path template. Blocked on T0.4 #22.
  - [#69 T7.4](https://github.com/kmeng/maestro/issues/69) — empty /
    disabled / error state templates + tests. Blocked on T7.3.
  - [#70 T7.5](https://github.com/kmeng/maestro/issues/70) — E2E
    verification (browser walk-through of all 4 states). Blocked on T7.4.

- **Three memory updates**:
  - `project_epic7_general_user_savings.md` — promoted from
    "design session pending" to "design approved 2026-05-10"; the
    "per-task opt-in" framing replaced with "per-task NOT in Web UI";
    sub-issue numbers + dependency state baked in for next-session
    boot.
  - `project_pure_worker_schemas.md` — decision recorded: this is
    NOT Epic 7 scope. User's framing: "work schema 完全是另外一件事
    情，如果是[问题]，我认为应该作为 Epic 5 的 bug. 晚点咱们修复
    bug." When prioritised, file as Epic 5 bug, not new epic, not
    Epic 7 sub-task.
  - `feedback_gh_body_file.md` — new feedback memory for the
    heredoc-leak gotcha (process learnings §).

- **Issue #65 body fixed**. Initial create + first edit both leaked
  literal `EOF` and `)` lines into the body via inline
  `gh issue edit ... --body "$(cat <<'EOF' ... EOF\n)"`. Caught via
  `gh issue view 65 --json body -q .body | tail -5`. Repaired with
  `gh issue edit 65 --body-file /tmp/epic7-body.md`. Sub-issues #66–#70
  were unaffected because `create_subissue.py` already takes a
  body-file argument internally.

## Decided

- **Epic 7 = Web UI savings page only (narrow scope)**. User picked
  option 1 of three offered scopings ("worker schema 完全是另外一件
  事情"). Sibling concerns get their own homes: worker-schema purity
  → Epic 5 bug; live refresh → follow-up; per-task in Web UI →
  follow-up only if user demand surfaces. The narrow scope makes
  Epic 7 a 5-task epic, ~5h of total work, all behind T0.4.

- **Calc layer extraction is the load-bearing structural decision**.
  `scripts/render_savings.py` currently mixes calculation and Markdown
  rendering. T7.1 extracts pure-calc functions (`read_rows`,
  `filter_superseded`, `compute_costs`, `group_by_task`,
  `group_by_role`, `_parse_dt`, `PROVIDER_RATES`) into a new module
  `bootstrap/savings.py`. Both the Markdown renderer (existing) and
  the Web UI route (T7.3) import from there. **Determinism gate**:
  re-rendered `docs/savings.md` must be byte-identical to the
  pre-refactor file. This is the regression contract that lets us
  refactor confidently — if the byte-diff is empty, the calc layer's
  external behaviour is preserved by definition.

- **Per-task is intentionally NOT a Web UI view**. Replaced "show
  conditionally based on task_id presence" (first draft) with
  "intentionally absent, follow-up if user demand surfaces". The
  cleaner answer to "what to do when general users don't need this
  feature" is "don't ship it", not "ship it gated". Conditional
  rendering is often the design smell of "I couldn't decide who
  this is for."

- **Snapshot rendering, no caching, no live refresh for v1**. Page
  computes on every request from JSONL on disk. JSONL is sub-MB at
  realistic scale; perf is fine. No SSE / htmx polling — manual
  refresh fits the actual usage rhythm (dispatches are user-triggered
  events, not a stream). Couples Epic 7 to nothing in Epic 3, which
  is good because Epic 3 isn't built. Re-evaluate if a user actually
  asks for live updates.

- **Per-time granularity = UTC calendar day, only**. Function
  signature is `group_by_time(rows, granularity="day")` from day one
  (forward-compat) but only `"day"` implemented; other values raise
  `ValueError`. This is the right shape of "design for extension
  without speculative implementation": the parameter is cheap to
  leave in place; the implementation is not added until needed.

- **No ADR for Epic 7**. The four technical decisions (calc-layer
  extraction location, snapshot-not-stream rendering, no caching,
  single granularity) are all small and reversible. ADR weight isn't
  warranted. If T7.3 implementation surfaces a non-obvious choice,
  add an ADR at that point. **Heuristic emerged**: ADR threshold is
  "long-term consequences" — new dependency, new role, interface
  change, storage format. Internal refactors that preserve external
  behaviour don't qualify.

- **Issue body authoring uses `--body-file`**. Inline heredoc is
  fragile; `--body-file` is the only safe path for multi-line bodies.
  Saved as feedback memory.

## Deferred

- **All T7.x implementation**. T7.1 + T7.2 are technically unblocked
  today (no Epic 0 dep) but session purpose was design-only. Next
  session can pick them up cold from the briefings.

- **Worker MCP schema purity** (`project_pure_worker_schemas.md`).
  Reframed today as Epic 5 bug, not Epic 7 scope. Will be filed as
  an Epic 5 bug issue when prioritised — confirm whether the
  workflow-coupling actually breaks shipped users in practice first.

- **Per-task table in Web UI**. If a user asks for it, file as a
  follow-up issue under Epic 7 or as a small follow-up epic. Today's
  decision is "absent until demanded", not "absent forever".

- **Live refresh** (htmx polling / SSE) for the savings page. Same
  shape as per-task: deferred until concrete demand.

- **Per-time granularity toggle** (week / month). Same shape.

- **Trend charts** (sparkline / line chart for per-time). Same shape.

- **Article + social-media post**. User signalled wanting both a
  knowledge-base summary (to Obsidian) and a publish-ready article.
  Pending the Obsidian vault path; angle/structure proposed in this
  session, draft to follow.

## Handoff for next session

- **Branch state**: on local `v0.0.3`, fully clean, fully pushed to
  `origin/v0.0.3`. No new branches today (design-only session). Next
  session opens to find the same `v0.0.3` head (`a55bb95` Merge
  docs/journal-2026-05-10-epic6-closed) plus whatever this journal +
  design + memory edits commit to.

- **Open issues at session end**: cumulative across all 4 arcs of
  2026-05-10:
  - **Closed today** (4 arcs cumulative): #21, #57, #58, #59, #63,
    #64, #61, #62, #60, #56 (10 closes including Epic 6 itself).
  - **Newly opened today (Epic 7 design session)**: #65 (Epic 7),
    #66 (T7.1), #67 (T7.2), #68 (T7.3), #69 (T7.4), #70 (T7.5).
  - **Other open**: tracking #2, #3; v0.0.3 epics #11–#16, #52
    (Epic 5 closed previously); v0.0.3 sub-issues #22–#51 (Epic 0/1/2/3).

- **Next implementation candidates**:
  1. **T7.1 (#66)** — calc extract. ~1h, no Epic 0 dep, no
     external blocker. The cleanest "do today" candidate.
  2. **T7.2 (#67)** — `group_by_time` + `resolve_log_path`. ~45min,
     after T7.1.
  3. **T0.4 (#22)** — Epic 0 web shell. Unblocks T7.3+. Was the
     previous arc's recommended next step too; still applies.
  4. **T1.1 (#26)** — Pydantic team config models. Already
     partially blessed by Session 1 librarian validation.
  5. **Wiki article repost** — still pending from previous arc;
     savings.md is now rich enough to back the claim.

- **Mandatory reading before any T7.x implementation** (briefings
  reference these explicitly; do not skip):
  - [docs/design/65-web-ui-savings-page.md](docs/design/65-web-ui-savings-page.md) — full design
  - [docs/design/56-effectiveness-page.md](docs/design/56-effectiveness-page.md) §3.1 — telemetry source context for the calc layer
  - Parent epic [#65](https://github.com/kmeng/maestro/issues/65)
  - Memory `project_epic7_general_user_savings.md`

- **Watchpoints carried forward**:
  - Latent async-dispatch timeout bug (no `asyncio.wait_for`) — still
    unfixed; today no dispatches at all so no new data
  - Librarian's strict-dict contract poorly documented to
    prompt-writers — observed yesterday, no exposure today
  - Renderer determinism needs CI gate — manual today, deferred to v0.0.4
  - Worker schema purity — now classified as Epic 5 bug, not Epic 7
  - **New**: `gh issue` multi-line body must use `--body-file`, not
    inline heredoc — saved as memory; verify with
    `gh issue view N --body-q .body | tail -5` after every edit

- **Article + Obsidian** is the explicit open thread at session end.
  Journal landing first; article draft to follow once the Obsidian
  vault path is confirmed by the user. Article tone: methodology /
  reflective, not narrative — outline proposed in-session.

## Process learnings

- **Inline heredoc into `gh issue create/edit --body "..."` leaks
  the EOF terminator into the issue body**. Caught via post-edit
  verification (`gh issue view 65 --json body -q .body | tail`),
  not from gh's exit code (which was 0 — the API call succeeded).
  Fix: always use `--body-file <path>` for multi-line bodies. The
  bash heredoc + command-substitution + multi-line `--body` argument
  is a fragile combination; the file-based path sidesteps the entire
  quoting problem. Saved as `feedback_gh_body_file.md`. Verification
  habit: `gh issue view N --json body -q .body | tail -5` after
  every multi-line body operation, until the file-based path is
  reflexive.

- **The "user vs general-user" framing rule paid off in practice**.
  Yesterday's `feedback_distinguish_user_from_general.md` was
  abstract guidance. Today applied it: design 65 §1 forced the
  audience-split treatment, which made it visible that per-task
  was a maestro-project need being projected onto general users.
  User's "2.2.4 拿掉" wasn't surprising — the rule had already done
  its work; the user was just reading the conclusion the rule
  pointed to. **Methodological framing rules earn their keep when
  they do work BEFORE the user has to**.

- **Conditional rendering is often the design smell of "I couldn't
  decide"**. First draft made per-task conditional ("only if
  task_id present"). Sharper move was to remove the surface
  entirely. The lesson: when designing for two audiences and unsure
  whether one needs a feature, ask "can we just not ship it for
  them?" before reaching for runtime gating. Conditional surfaces
  carry forever-cost (test paths, doc, edge cases); absent surfaces
  carry zero cost.

- **Mid-design revision requires cross-section sweep, not local
  patch**. Per-task removal touched §1.1, §1.2, §2.2, §2.3, §3.2,
  §3.5, §4, §6, §7, §9 of the design doc — 10 sections out of 10.
  Patching only the §2.2 reference would have left the doc
  internally inconsistent (§3.2 ctx still passing per_task into the
  template, §9 still asking what to link task_id to, etc.). The
  rule: when removing a concept from a design, grep the doc for the
  concept and revisit each match. Same applies to renames and
  scope shifts.

- **Pre-implementation design phase is decision-cheap**. Today
  baked in ~6 architectural decisions (narrow scope, calc-layer
  extraction, no-per-task, no-cache, no-live-refresh, granularity
  shape, no-ADR) without writing any code. Each would have been
  more expensive to revise during implementation: the calc-layer
  extraction in particular would have been painful to undo if T7.3
  had been written first against a duplicated calc surface. **The
  cost of design-phase decisions is the time to articulate them;
  the cost of implementation-phase decision reversals is the time
  to articulate them PLUS the code rework PLUS the test rework**.

- **Reuse-before-reinvent saved real time**. Sub-issue creation
  needed → `scripts/create_subissue.py` already existed (from issue
  #17 governance amendment work). Found via `head -60` before
  drafting an alternative. Cost of the discovery: ~30 seconds.
  Cost of building a parallel helper: ~15 minutes. The lesson is
  about the search habit, not the specific tool: **before writing
  workflow tooling, run the obvious grep**.

- **Memory written DURING the work (continued)**. The
  heredoc-leak feedback memory was written within 2 minutes of the
  diagnosis, while the failure mode was concrete. By contrast, if
  end-of-session batched, the next session might know "watch out
  for gh body issues" but not "always use `--body-file` and
  verify with `tail -5`". Specificity decays fast in batched
  retrospectives. Per yesterday's process learning: write the
  memory at the surfacing moment, then continue.

- **Design-doc length is a function of decision count, not feature
  size**. Design 65 is ~280 lines for ~5 hours of implementation
  work. Design 56 (Epic 6) was ~390 lines for ~10 hours. The ratio
  is roughly stable: ~30-50 lines of design per hour of
  implementation. Underspecification produces implementation drift;
  overspecification produces unread bytes. Today's doc landed at the
  appropriate length because each section corresponded to one
  decision the future implementer would otherwise have to make
  ad-hoc.

- **Open questions in design docs should be EITHER answered now OR
  marked as "implementer chooses"**. Design 65's §9 lists 2 open
  questions; both are tagged "defer to T7.3 implementation, out of
  scope here". This is honest deferral — the implementer has
  permission to decide without coming back to the doc author.
  Worse pattern: open questions left as questions with no instruction
  about who decides. Either the doc author decides, or they
  explicitly delegate. Don't leave the question vacant.

- **One session, one purpose**. This session was design-only and
  produced no code despite T7.1 being technically doable today.
  The discipline: don't blur design → implementation in the same
  session, even when the next step is small. Design-session
  artifacts (doc + epic body + sub-issues + memory) are best
  finished cleanly so the next session can audit them cold.
  Implementation-session artifacts (commits + tests + journal
  entries) live on a different cadence. Mixing them produces
  half-finished design AND half-finished implementation.
