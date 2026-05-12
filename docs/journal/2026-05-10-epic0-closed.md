# 2026-05-10 — Epic 0 Closed

> Fifth arc of the day, fourth journal file. Sibling to `2026-05-10.md`
> (morning + afternoon), `2026-05-10-epic6-closed.md` (evening),
> `2026-05-10-epic7-design.md` (late evening / night). This very-late
> arc closed Epic 0 in 4 task-PRs (T0.4 → T0.5 → T0.6 → T0.7), tripped
> a workflow-violation recovery mid-flight, and produced a smoke
> harness that doubles as the documented Epic-0 acceptance contract.

## Session 5 — very late (CST)

The handoff from `2026-05-10-epic7-design.md` listed T7.1 as the
cleanest "do today" candidate. The user re-aimed: T0.4 was the actual
next-up because it sat under Epic 0, the foundation epic, and design 65
had explicitly noted T0.4 as the unblocker for T7.3+. Pivoting from the
written handoff to the user's living priority is itself a process
moment — the journal's "next-step" suggestions are advisory, not
binding. From there the session ran T0.4 → recovery from a workflow
violation → T0.5 + T0.6 (parallel coder dispatches, sequential
branches) → T0.7 (Epic 0's E2E gate). Net: Epic 0 7/7 closed,
parent issue [#12](https://github.com/kmeng/maestro/issues/12) closed,
`v0.0.3` head moved from `a55bb95` to `614e531`.

## Done

- **T0.4 ([#22](https://github.com/kmeng/maestro/issues/22)) — empty-shell page + vendored htmx**.
  Branch `feature/22-empty-shell-htmx`, commit `f493216`, merge `24d2af0`.
  `maestro/webui/__init__.py` extended with `Jinja2Templates` + `StaticFiles`
  mount; new `templates/index.html` (Chinese hero `等待第一支乐章`, system
  fonts + dark-mode CSS vars, footer renders `maestro.__version__`); htmx
  2.0.4 vendored at `static/vendor/htmx.min.js` (50917 bytes); 5 new tests
  in `tests/test_webui.py` (10/10 total). Coder dispatch (`deepseek-v4-pro`,
  147s / 7001 tok) produced full code matching spec; one starlette
  `TemplateResponse` signature drift (`(name, context_dict)` vs new
  `(request, name, context)`) caught by tests, fixed inline. Reviewer
  shadow (68s / 3898 tok) verdict pass.

- **Workflow-violation recovery** (mid-T0.4). After T0.4 commit landed,
  pushed `feature/22-empty-shell-htmx` to remote and opened
  [PR #71](https://github.com/kmeng/maestro/pull/71) — both wrong per
  the project's "feature → local merge to v0.0.3 → push v0.0.3, no PR
  except v0.0.3 → main releases" workflow. User caught it
  ("按照咱们的约定应该是在本地先 merge"). Recovery in 6 steps:
  (1) `gh pr close 71`, (2) `git push origin --delete feature/22-...`,
  (3) `git merge --no-ff feature/22-... v0.0.3`, (4) `git push origin
  v0.0.3`, (5) delete local feature branch, (6) manually close
  [issue #22](https://github.com/kmeng/maestro/issues/22). The original
  branch-workflow memory only covered worktree `claude/*` temp branches;
  it didn't say "named feature branches also stay local" explicitly,
  which is why the violation happened. Memory rewritten as 8-step
  procedure with the T0.4 incident logged in the **Why** section as a
  deterrent reference.

- **Switch to Chinese for orchestrator output**. User's same correction
  message: "另外，咱们应该是中文交互." Honored from that turn forward;
  no impact on code/comment language (still English per
  `feedback_code_quality_baseline.md`).

- **T0.5 ([#23](https://github.com/kmeng/maestro/issues/23)) — maestro-webui launcher + port-conflict + minimal pyproject.toml**.
  Branch `feature/23-launcher-port-conflict`, commit `0537007`, merge
  `d7f3ef9`. Three deliverables: (a) new minimal PEP 621 `pyproject.toml`
  with setuptools backend, `[project.scripts] maestro-webui =
  "maestro.webui.launcher:main"`, package-data for templates + vendor;
  (b) `maestro/webui/launcher.py` — `read_preferred_port`
  (settings.yaml → DEFAULT_PORT 19830 fallback on missing/malformed/
  non-int), `_port_is_free` (bind-and-close on 127.0.0.1), `find_free_port`
  (preferred → +10 scan, RuntimeError with `--port` hint at exhaustion),
  `main` (argparse `--port`, exit 2 on exhaustion, blocks on uvicorn);
  (c) 12 unit tests using a self-defined `unused_tcp_port` fixture
  (avoided pulling in `pytest-asyncio` for one fixture). Coder dispatch
  (114s / 5996 tok) — output had spec-required `unused_tcp_port` /
  `unused_tcp_port_factory` fixture references that don't exist in
  vanilla pytest; orchestrator added local fixtures inline rather than
  add a dep. Reviewer (95s / 4425 tok) pass. Smoke: `pip install -e .`
  installed `maestro-webui` console_script at `/opt/anaconda3/bin/maestro-webui`,
  `--help` returned correctly.

- **T0.6 ([#24](https://github.com/kmeng/maestro/issues/24)) — dev_emit_dispatch.py stub**.
  Branch `feature/24-dev-emit-dispatch-stub`, commit `83b4afd`, merge
  `3502cf3`. New `scripts/dev_emit_dispatch.py` (chmod +x): argparse
  `--project PATH` (required, must be existing dir) + mutex
  `--success/--failure` (default success); writes one JSON line per
  invocation to `<project>/.maestro/logs/dispatch.jsonl`; event has
  `ts/outcome/tool/note` with `note` text "stub event awaiting Epic 3
  T3.1 schema" so the stub-ness is unmistakable in any future log
  reader. 6 unit tests via `importlib.util` (script not on sys.path
  normally). Coder (91s / 4218 tok) flagged in concerns a suspected
  mutex+default conflict — orchestrator analyzed argparse semantics
  (defaults don't trigger mutex), didn't fix; tests confirmed. Reviewer
  (78s / 3361 tok) pass. Smoke: `mktemp -d`, ran script twice
  (`--success` then `--failure`), got 2 JSONL lines with correct
  outcomes.

- **T0.7 ([#25](https://github.com/kmeng/maestro/issues/25)) — Epic 0 end-to-end verification**.
  Branch `feature/25-epic0-e2e-verification`, commit `d68bd36`, merge
  `614e531`. Two artifacts: (a) `tests/smoke/epic0_smoke.sh` (chmod +x,
  150 lines) — 8 automated checks (install / console_script / launcher
  starts + URL / `GET /` Chinese hero copy / vendored htmx / `/health`
  schema / port-freed-on-kill / port-conflict fallback to 19831), bash
  with `set -euo pipefail` + trap cleanup, no new deps beyond bash +
  curl + python3; (b) `tests/smoke/epic0.md` (107 lines) — full AC
  checklist covering AC1 (clean install), AC2 (v0.0.2 regression — MCP
  `coder` from a Claude Code session, with note that `cheap_code_gen` →
  `coder` rename happened in T5.1), AC3 (port-conflict), AC4 (this doc
  itself), plus manual browser visual + dev_emit_dispatch smoke.
  Coder (227s / 8059 tok) bash output; orchestrator added a single
  defensive guard (`[ ${#LOG_FILES[@]} -gt 0 ]` before iterating, for
  bash 3.2 + `set -u` empty-array compatibility). No reviewer dispatched
  — reviewer's pass/fail framing doesn't apply to glue + docs. Smoke:
  ran the script itself, **8/8 PASS**.

- **Epic 0 ([#12](https://github.com/kmeng/maestro/issues/12)) closed**.
  All 7 sub-tasks T0.1–T0.7 closed. Comment on parent enumerates each
  sub-task with its outcome and links the smoke harness as the
  acceptance contract going forward.

- **Memory updates**:
  - `feedback_branch_workflow.md` — full rewrite. Old version (3 days
    old, dated 2026-05-07) only covered worktree `claude/*` temp
    branches. New version is an 8-step procedure for any feature-branch
    work in maestro, with the T0.4 violation incident in the **Why**
    section as a referenceable deterrent. The old "not pushing claude/*"
    rule is preserved, just generalized.
  - `MEMORY.md` — index line for branch workflow updated to reflect new
    title; index line for Epic 7 updated to note T0.4 is closed and
    T7.3+ is now unblocked too.

## Decided

- **Workflow violation gets 6 explicit recovery steps + memory rewrite,
  not just an apology**. The recovery sequence (close PR → delete
  remote branch → local merge → push v0.0.3 → delete local branch →
  manually close issue) is now documented in the rewritten memory's
  "如果 PR 已误开" recovery section. The point: a violation that
  produces a referenceable recovery procedure is more durable than a
  violation that produces only a "won't happen again" promise. The
  next contributor (or the next AI session) gets a working-out-loud
  recovery path, not a stigma.

- **`pyproject.toml` is created in T0.5, not deferred to Epic 4
  (packaging)**. T0.5's first AC requires the command `maestro-webui`,
  which can be ergonomically delivered only via `[project.scripts]`.
  Surfaced the scope-signal to the user before writing code (option A
  minimal pyproject vs option B `python -m` vs option C defer to
  Epic 4); user chose A. Decision rationale: the v0.0.3-pre debt of
  "maestro is not pip-installable" gets paid down naturally as part of
  T0.5; Epic 4 will extend (wheel build, classifiers, long_description),
  not start over. No ADR — the decision is small + reversible + adopts
  the standard `setuptools` backend, no novel commitments.

- **T0.6 coder's concern was wrong; orchestrator analyzed before
  patching**. Coder flagged a suspected argparse mutex+`default=True`
  conflict ("the test would fail"). Orchestrator analyzed argparse
  source semantics (mutex group fires only on user-supplied args,
  defaults don't count) and chose to write the file as-coder-output,
  letting tests be the arbiter. Tests passed 6/6. Lesson: take coder's
  concerns as informational priors, not as patches-to-apply. The cost
  of inverting the concern's polarity (reading argparse semantics
  yourself) is small; the cost of a false-positive fix is larger
  because it warps the design.

- **`epic0_smoke.sh` is BOTH the acceptance harness AND the smoke
  artifact**. Considered writing a separate pytest version of the same
  checks; rejected. The bash script's value is that it runs as both
  CI-runnable verification AND the documented procedure (the markdown
  literally says "run this script" rather than re-listing the steps).
  A pytest version would duplicate the steps and create a third source
  of truth. The single-source-of-truth principle wins over the
  test-framework-uniformity principle here.

- **Manual portion of T0.7 explicitly named the v0.0.2 → v0.0.3 rename
  (`cheap_code_gen` → `coder`)**. Without that line, a future user
  reading older docs would hit a "tool not found" and not know to
  substitute. One sentence in `tests/smoke/epic0.md` saves an
  afternoon for whoever reads it cold.

## Deferred

- **Browser-visual portion of T0.7 manual checklist**. The smoke script
  doesn't drive a browser; the user (or a future contributor) walks
  through the markdown checkboxes in `epic0.md` when running the full
  smoke. Not a blocker for closing T0.7 / Epic 0 — the manual checklist
  is the artifact, the human is the runtime.

- **MCP `coder` regression smoke from a real Claude Code session**.
  Same shape: documented in `epic0.md`, requires a Claude Code session,
  deferred to whoever does the next manual smoke pass. Not blocking
  Epic 0 close because the v0.0.2 code path was untouched by
  T0.1–T0.7; the regression check is a defensive "trust but verify."

- **Epic 7 implementation**. T7.1 / T7.2 still unblocked from yesterday;
  T7.3+ now unblocked too as a downstream effect of T0.4 closing.
  Pencilled-in "next session" candidate.

- **`coder` worker output drift fix-up loop**. Two small drifts
  encountered today (T0.4 starlette signature, T0.5 missing pytest
  fixture). Both caught by tests / inline analysis and fixed in <2
  minutes; net impact on session time was negligible. Not promoted to
  a memory because the drifts were both spec-precision misses (one in
  `templates.TemplateResponse` API, one in spec naming a fixture
  pytest doesn't ship), not coder-quality issues. If the rate climbs,
  reconsider.

## Handoff for next session

- **Branch state**: on `v0.0.3`, fully clean, head `614e531`, fully
  pushed to `origin/v0.0.3`. No local feature branches (all deleted
  after merge). 148 unit tests passing; 8/8 epic0 smoke checks passing.

- **Open issues at session end**:
  - **Closed today (this arc)**: #22 (T0.4), #23 (T0.5), #24 (T0.6),
    #25 (T0.7), #12 (Epic 0 parent). 5 closes.
  - **Open**: tracking #2, #3; v0.0.3 epics #11, #13–#16; v0.0.3
    sub-issues across Epics 1, 2, 3 (#26–#51); Epic 7 sub-issues
    #66–#70; governance #17.

- **Next implementation candidates**:
  1. **T7.1 ([#66](https://github.com/kmeng/maestro/issues/66))** —
     Epic 7 calc extract, ~1h. Cleanest solo task.
  2. **T1.1 ([#26](https://github.com/kmeng/maestro/issues/26))** —
     Epic 1 Pydantic team config models. Now unblocked from Epic 0.
  3. **T7.2 (#67)** — group_by_time + resolve_log_path. After T7.1.
  4. **T7.3 (#68)** — Web UI route `GET /savings`. T0.4 unblocked it
     today; can run after T7.1+T7.2.

- **Mandatory reading before any T1.x work**: design 13
  (`docs/design/13-epic1-team-composition.md`), ADR-0004 (team config
  format), parent epic #13. Before T7.x: design 65 + the now-merged
  design 12 sections that T0.4 referenced (templates, static layout).

- **Watchpoints carried forward**:
  - Latent async-dispatch timeout bug (no `asyncio.wait_for`) — still
    unfixed; today no async dispatches that revealed it.
  - Worker MCP schema purity (`scribe` requires GitHub-issue fields) —
    still classified as Epic 5 bug, not blocking.
  - **New**: smoke script timing assumes uvicorn cold-start <10s.
    Generous on local dev; if CI machines run slower, raise the polling
    window in `epic0_smoke.sh` checks 3 + 8.
  - **New**: `pyproject.toml` is now load-bearing; any future
    `pip install -e .` is a smoke-relevant action. Watch for
    `package-data` regressions if templates/vendor get reorganized.

- **Article + Obsidian** for this arc is in flight at session end —
  same pattern as the past two arcs.

## Process learnings

- **Workflow violations are the cheapest source of memory updates**.
  The T0.4 push-to-remote + open-PR mistake produced a more useful
  memory than a clean session would have. The original 2026-05-07
  branch-workflow memory used phrases like "named feature branches"
  without saying explicitly "feature branches in maestro stay local
  too" — ambiguous in a way that only became visible when violated.
  Rewriting it after the fact, with the incident logged in the **Why**,
  produces a sharper rule than would have come from any number of
  "make sure to ..." pre-emptive instructions. The rule: when a
  violation happens, don't just apologize and proceed — return to the
  memory that was supposed to prevent it and ask "why didn't this
  catch me?"

- **The 6-step recovery procedure is itself the durable artifact**.
  After the user pointed out the violation, the recovery wasn't
  "undo the push and ask what to do next" — it was "here's the exact
  6 steps, each is a state change, please confirm and I execute."
  That recovery sequence is now in the memory. Next time someone (AI
  or human) makes the same mistake, they don't need to re-derive the
  recovery; they look it up. **Mistakes that produce procedures
  outlive themselves**.

- **Spec-precision pays off in coder one-shot rate**. The T0.5 spec
  named the 12 tests by name + behavior + which fixture each used,
  the T0.6 spec named the 6 tests + the import shim + the json fields
  + the chmod step. Both came back essentially run-ready (one fixture
  shim added inline for T0.5, zero for T0.6). The cost of writing the
  spec at this granularity is ~5 minutes of orchestrator time;
  the cost of a coder coming back vague-good is a re-dispatch cycle
  (~3 minutes) plus reading-and-judging the diff (~2 minutes). At
  the margin, granular specs win.

- **Coder concerns are priors, not patches**. T0.6's coder flagged
  a "this might fail" concern that was actually wrong. The
  orchestrator-side discipline: read the concern, check the actual
  semantics (often a 30-second mental walk through the API), and
  decide. Writing the worker's suggested fix without checking is
  worse than ignoring the concern, because the suggested fix bakes
  the misunderstanding into the artifact. Concern → analysis → keep
  or fix, never concern → fix.

- **Parallel coder dispatches with sequential branch landing**.
  T0.5 and T0.6 dispatched simultaneously (114s + 91s overlapping);
  orchestrator wrote the T0.5 branch + tests + reviewer dispatch
  serially after T0.5 came back, did the same for T0.6 next.
  No worker idle time, no orchestrator idle time, no branch
  conflicts (different files, sequential merges). The parallelism
  pattern: dispatch is parallel; landing is serial; the gap between
  the two is where the orchestrator does its judgment work.

- **Smoke harness as both contract and execution**. The bash script
  is the documented procedure; the markdown is just signage. A
  separate pytest version was considered and rejected — three
  copies of the same logic (bash, pytest, markdown checklist)
  would diverge. The single bash script is the source of truth;
  the markdown points to it. **When a check is the contract,
  write it once and reference it everywhere; don't duplicate the
  logic into the documentation.**

- **The handoff is advisory, not binding**. The previous arc's
  journal listed T7.1 as the cleanest next task. The user re-aimed
  to T0.4 (the foundation epic that the Epic 7 design itself
  depended on as a prerequisite). The journal's next-step list is
  a snapshot of the writer's then-best understanding; the user's
  living priority can override. The orchestrator's job at session
  start is to read the handoff AS context, then verify against the
  user's current ask, not assume the handoff is the plan.

- **Closing an epic produces a load-bearing artifact for the next
  one**. T0.7's smoke script doesn't just verify Epic 0 today; it
  becomes the regression gate for any future change to the Web UI
  process or shared paths. Future PRs that touch `maestro/webui/`
  or `maestro/paths.py` should run `bash tests/smoke/epic0_smoke.sh`
  before merging. Without T0.7, every such PR would re-derive the
  smoke procedure ad-hoc. **An "E2E verification" task is not a
  formality at the end of an epic — it's an asset that pays interest
  to every later epic.**
