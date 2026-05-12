# Maestro Build Log

A transparent record of how Maestro was built, including which AI models contributed which parts and what they cost.

This log is the project's most important narrative artifact: it proves Maestro works by showing Maestro built itself.

---

## v0.0.1 — Bootstrap (hand-written)

**Date**: 2026-05-07
**Phase**: Bootstrap (pre-self-hosting)
**AI cost**: $0 (Claude Pro/Max subscription only)

The minimum viable foundation. Hand-designed by Claude Opus in a claude.ai conversation with the maintainer; committed via Claude Code. From v0.0.2 onward, all features are developed using Maestro itself.

### What was built

- Project governance (`docs/governance.md`)
- Architectural principles (`docs/architecture.md`)
- Claude Code operating rules (`CLAUDE.md`)
- Bootstrap MCP server (`bootstrap/maestro_server.py`):
  - Single tool: `cheap_code_gen` routing to DeepSeek-Coder
  - Structured worker response format (reasoning + output + concerns)
  - JSONL audit logging
  - Timeout and graceful error handling
- Quick start guide (`bootstrap/QUICKSTART.md`)

### AI contributors

- **Claude Opus 4.7** (claude.ai conversation): All design, architectural decisions, and code drafts
- **Claude Code** (local CLI session): File creation, git operations, PR submission

### Lessons learned

_To be filled in after first real-world use._

---

## v0.0.2 — Self-hosting era (in progress)

**Phase**: Self-hosting (Maestro extending Maestro)
**AI cost**: TBD (will sum at release)

This is the first version where Maestro is actively used to develop itself. Each commit from here on includes `Co-authored-by` attribution for any AI model that contributed substantive code.

### #6 — Server self-loads config from .env

**Date**: 2026-05-07 → 2026-05-08
**Branch**: `feature/6-env-loading`

What was built:
- Zero-dep `.env` loader at server startup (~15 lines, stdlib only)
- `.env.example` template at repo root as the user-copyable starting point
- Actionable error messages that name the exact next step (path to copy / line to add) instead of bare "missing"
- QUICKSTART rewrite covering both Claude Code (`claude mcp add`) and Claude Desktop (`claude_desktop_config.json`) — neither now requires the user to put the API key into client-side config

Why this came first in v0.0.2:
- v0.0.1 validation surfaced two setup gotchas (SOCKS proxy + MCP env propagation, captured in closed issue #5). The proper fix removed the second gotcha entirely by moving the secret-loading responsibility into the server itself.
- Resolves the mismatch between architecture P3 (secrets in env vars only) and the practical reality that MCP client configs *are* config files.

AI contributors:
- **Claude Sonnet** (Claude Code session): design doc, server loader implementation, error-message redesign, QUICKSTART rewrite
- Maintainer: scope decisions (zero-dep, `.env`-overrides semantics, repo-root location, minimal-change principle), branch model (B — release/feature/task three-tier), every approval gate

Honest dogfooding note:
- `cheap_code_gen` was **not** invoked for this feature. The change was small enough that splitting into worker tasks would have added more orchestration overhead than it saved. v0.0.2's BUILD_LOG should track which features actually used the dispatch path so we have a real signal on when self-hosting starts paying off.

Process notes:
- Three-tier branch model (release `v0.0.2` → feature `feature/6-env-loading` → local-only task sub-branches) introduced. `docs/governance.md` doesn't yet describe this; tracked as design-doc OPEN-5, to be backfilled in a dedicated issue post-release.
- Closed predecessor #5 captures the reasoning trail for why we chose `.env`-loading instead of documenting `--env`.

### Lessons learned (running)

_v0.0.2 lessons will accumulate as features ship._

---

## v0.0.3 — Worker fleet & Web UI for end users

**Date**: 2026-05-12 (release-cut)
**Phase**: Self-hosting at scale (orchestrator dispatches the fleet, not just a single worker)
**AI cost (measured, via per-dispatch telemetry)**: **$0.59 worker** vs **$45.73 Opus baseline** → **$45.13 saved (98.7%)** across 127 dispatches over 52 closed tasks.

### Release summary

v0.0.3 closes 5 P0 epics:

- **Epic 0** — local Web UI skeleton (FastAPI launcher + Jinja2 templates + vendored htmx + port resolution)
- **Epic 1** — team composition (team.yaml + Web UI wizard + standing-config view)
- **Epic 2** — project scaffolding (template-driven new-project setup from the Web UI)
- **Epic 3** — team observability (history view + live dispatch SSE + problem panel)
- **Epic 7** — Web UI savings page (general-user view of own dispatch costs at `/savings`)

Epic 4 (packaging + distribution) deferred to v0.0.4+ as P1.

v0.0.3 also introduced three new worker roles alongside `coder` (renamed from `cheap_code_gen`): `librarian` (reads long docs), `reviewer` (judges code against a spec), `scribe` (drafts commits and PR bodies). Async dispatch (ADR-0009) removes the MCP 60-second synchronous-call ceiling.

### Headline measured cost savings

| Role | Dispatches | Total tokens | Total worker $ | Total est. Opus $ |
|---|---|---|---|---|
| Coder | 43 | 428,597 | $0.33 | $22.08 |
| Librarian | 20 | 176,229 | $0.02 | $6.10 |
| Reviewer | 42 | 286,813 | $0.20 | $13.50 |
| Scribe | 22 | (counted in role-mix) | $0.04 | $4.05 |

**98.7% saved** vs an all-Opus baseline of $45.73 across the entire epic-implementation history (52 closed tasks, 127 dispatches). Per-task evidence in [`docs/savings.md`](docs/savings.md); general-user view at `/savings` in the Web UI; methodology in [`docs/savings-methodology.md`](docs/savings-methodology.md).

⚠ Transparency note: Epic 7's worker-cost ratio under-counts the actual work. T7.2 / T7.3 / T7.4 were hand-authored before the **"ALL code goes to coder — no carve-outs"** discipline rule was laid down (mid-Epic 7) and applied to T7.5 + fix #86. The drift is documented in [`docs/journal/2026-05-12-epic7-close-and-coder-rule.md`](docs/journal/2026-05-12-epic7-close-and-coder-rule.md). Future epics under the new rule will show truer ratios.

### What shipped

- **Fleet (Epic 5)** — coder / librarian / reviewer / scribe MCP tools with async dispatch (`job_id` polling) + structured response banners.
- **Web UI shell (Epic 0)** — `maestro-webui` console-script entry point, port resolution (CLI flag > user settings > default), bound to 127.0.0.1, vendored htmx, no CDN at runtime (ADR-0002).
- **Team composition (Epic 1)** — `team.yaml` read/write API, wizard, standing-config view; team templates ship via the scaffold pipeline.
- **Project scaffolding (Epic 2)** — per-project setup from the Web UI, including `.maestro/` layout and starter team.yaml.
- **Observability (Epic 3)** — `/history` (reverse-chronological dispatch view), `/api/dispatch_log/stream` (SSE for live updates), `/problems` (error / refused / fallback grouping with CTAs), Chinese labels for dogfooding-era views.
- **Savings page (Epic 7)** — English `/savings` route with per-role + per-time tables for general users; degraded states (empty / disabled / error); shared `maestro/savings.py` calc layer.
- **Dispatch telemetry (T0.3 onwards)** — append-only `docs/data/dispatch-log.jsonl` with `started_at`, `wall_s`, `prompt_tokens`, `completion_tokens`, `total_tokens`, `task_id`, `issue_number`, `tool`, `model`, `is_estimate`, `supersedes`. Markdown renderer at [`scripts/render_savings.py`](scripts/render_savings.py); Web UI consumer at [`maestro/webui/savings_view.py`](maestro/webui/savings_view.py); single calc core at [`maestro/savings.py`](maestro/savings.py).
- **Process discipline** — 11 memory entries codifying orchestrator behaviour; the most consequential mid-release rule update was `feedback_coder_file_modification` ("ALL code writing goes to coder — no carve-outs").

### AI contributors

- **claude-opus-4-7** (orchestrator) — all design pass-2 reviews, dispatch decisions, integration commits, journal authoring, memory authoring, mechanical chain (commit / merge / push / close).
- **deepseek-v4-pro** (coder + reviewer) — code generation under spec; pass/concerns/fail verdicts on generated code; ~80% of generated implementation across Epics 0–3 + 5 + 7 (excluding the T7.2–T7.4 hand-author window).
- **deepseek-v4-flash** (librarian) — long-document reading (designs, ADRs, journal entries) producing summary banners that never enter orchestrator context.
- **deepseek-v4-pro** (scribe — promoted from shadow on 2026-05-11) — commit messages, PR bodies, issue close comments where dispatched.
- **Maintainer** — every approval gate, scope decisions, mid-release rule corrections (notably the "ALL code goes to coder" rule), branch-workflow decisions.

### Lessons learned

1. **Per-dispatch telemetry was the right call.** T0.3's instrumentation produced 127 real data points that replaced the v0.0.2-era "estimated 56% saving" guess with measured "98.7% saving". The savings page and the Markdown evidence file are both deterministic re-derivations from the same JSONL — there is no separate ledger to drift.

2. **"ALL code goes to coder — no carve-outs."** Hand-author drift across 3 consecutive tasks (T7.2 / T7.3 / T7.4) showed that quality stays green under hand-author because reviewer doesn't audit the should-have-dispatched decision. The rule was tightened mid-Epic 7 and applied to T7.5 + fix #86. Future epics will show truer worker-cost ratios.

3. **Smoke tests catch what reviewer misses.** Both T3.10 (Epic 3 smoke) and T7.5 (Epic 7 smoke) caught real production bugs that 4 reviewer passes had missed each time. Reviewer is necessary but not sufficient; smoke that exercises the **installed** entry point (not pytest-with-rootdir-injection) is non-redundant.

4. **Application code belongs in the installed package.** Fix #86 relocated the savings calc layer from `bootstrap/savings.py` (excluded from wheel) to `maestro/savings.py`. Original design choice was driven by proximity to `bootstrap/maestro_server.py` but ignored wheel-scope. Going forward: anything consumed by an installed entry point lives under `maestro/`.

5. **Mid-release course corrections are fine.** The new "ALL code to coder" rule landed during Epic 7, was applied immediately, and recorded transparently in the journal. The release ships with the rule fully in effect and the historical drift documented rather than hidden.

6. **Four worker roles is enough for v0.0.3.** Open question for v0.0.4: do we need a fifth role (writer / technical-doc) for creative writing like ADRs and methodology pages? Tracked in `project_writer_worker_gap` memory; not yet a blocker.

### 🎉 Historical milestone — first end-to-end dispatch fleet run (T0.2 / #20)

**Date**: 2026-05-09
**Branch**: `feature/20-env-loader-credentials` → merged into `v0.0.3` via `--no-ff` (merge commit `dc39235`)

What happened:
- T0.2 itself is small: extend the v0.0.2 `.env` loader to fall back to `~/.maestro/credentials.env`, with precedence process env > project `.env` > user file. 89 lines + 10 unit tests.
- What's notable is the construction process: it was the first implementation task in which **every** Epic 5 worker role was dispatched end-to-end by the orchestrator.
  - **librarian × 2** (parallel) — read `docs/design/12-epic0-web-ui-skeleton.md` and `docs/adr/0003-shared-state-file-layout.md`. Neither document entered the orchestrator's context window.
  - **coder × 1** — generated `maestro/env_loader.py` + `tests/test_env_loader.py`. 116s wall, 6066 tokens, deepseek-v4-pro. One concern accepted at integration ("file-empty vs file-missing log conditions").
  - **reviewer × 1 (shadow)** — verdict `pass`, no findings, no missed_requirements. Orchestrator's parallel shadow reached the same verdict.
  - **scribe × 1 (shadow)** — drafted Conventional Commits message + PR body with co-authorship attribution and `Closes #20` line. User selected the worker output verbatim.
- Orchestrator code: exactly one piece of original work — the bootstrap integration replacing the inline `_load_dotenv` with a call to `load_credentials()`. `sys.exit` semantics + cross-file coordination is orchestrator territory.

This was the recursion point: Maestro using Maestro to build Maestro, with every Epic 5 role earning its keep on its first real task. The dogfooding loop closes here — from this point forward dispatch became the default.
