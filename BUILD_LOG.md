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

## v0.0.3 — Worker fleet & Web UI skeleton (in progress)

**Phase**: Self-hosting at scale (orchestrator dispatches the fleet, not just a single worker)
**AI cost**: TBD (per-dispatch telemetry begins T0.3; see Lessons learned)

v0.0.3 introduces three new worker roles alongside `coder` (renamed from `cheap_code_gen`): `librarian` (reads long docs), `reviewer` (judges code against a spec), `scribe` (drafts commits and PR bodies). The orchestrator's job becomes dispatch + integration + decision rather than direct production. Async dispatch (ADR-0009) removes the MCP 60-second synchronous-call ceiling.

### 🎉 Milestone — first end-to-end dispatch fleet run (T0.2 / #20)

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
- 78 tests pass total (10 new env_loader + 10 paths + 58 workers). Bidirectional smoke verified: project-`.env`-only resolution unchanged (v0.0.2 compat); isolated user-file fallback resolves DEEPSEEK_API_KEY end-to-end.

Estimated cost savings on this single task vs an all-Opus baseline:

| | Actual (with dispatch) | Hypothetical (all-Opus) |
|---|---|---|
| Opus input tokens | ~30K | ~80K |
| Opus output tokens | ~5K | ~10K |
| Worker tokens (DeepSeek) | ~45K | 0 |
| Estimated cost (USD) | ~$0.85 | ~$1.95 |
| **Savings** | — | **~$1.10 / ~56%** |

Estimates only — librarian's banner doesn't carry token usage and Opus's real input is reduced by prompt caching, so the all-Opus baseline could be 20–30% lower. **Per-dispatch wall + token telemetry begins T0.3** (see Lessons learned). By v0.0.3 ship, ~30 real data points will replace this estimate with a regression.

AI contributors:
- **claude-opus-4-7** (orchestrator) — task analysis, plan, dispatch decisions, integration into bootstrap, verification
- **deepseek-v4-pro** (coder) — `maestro/env_loader.py` and `tests/test_env_loader.py`
- **deepseek-v4-flash** (librarian, reviewer, scribe) — design-doc reading, code review (shadow), commit/PR drafting (shadow)
- Maintainer: scope decisions, dogfooding-philosophy correction (one-off shadow protocol → "worker dispatch is default for code work"), branch-workflow correction during merge (no PR; local merge → push v0.0.3), every approval gate

Why this is recorded as a milestone:
- It is the project's recursion point: Maestro using Maestro to build Maestro, with every Epic 5 role earning its keep on its first real task. The dogfooding loop closes here — from this point forward dispatch is the default, not the experiment.

### Earlier v0.0.3 work — pending backfill

T0.1 (`maestro/paths.py` + bootstrap shim) and Epic 5 (#52: librarian + reviewer + scribe + rename + ADRs 0008/0009) shipped before this BUILD_LOG entry was opened. Both are documented in `docs/journal/2026-05-09.md` (Sessions 1 + 2) and in their respective merge commits, but a proper retrospective belongs here. To be backfilled.

### Lessons learned (running)

- **Per-dispatch token + wall-time telemetry starts T0.3.** T0.2 demonstrated savings by estimate; from T0.3 onward each dispatch's banner (`[<tool> dispatch — <model> — Xs — N tokens]`) is recorded in the session journal. The roll-up at v0.0.3 ship replaces the estimate with measurement.
- **The orchestrator's job is dispatch + decision.** A clear, detailed spec is the *best* candidate for dispatch, not a worse one (corrected from a midday wrong framing during T5.2 — see journal). Workers are cost-saving tools, not creative collaborators. Orchestrator steps in only when worker can't cover.
- **Infrastructure obstacles are paid down, not bypassed.** When T5.2's coder dispatches hit the MCP 60s timeout, T5.3 fixed the timeout (async + job_id) instead of letting "I'll just write it directly" become precedent.
