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

---

## v0.1.0 — First downloadable release

**Date**: 2026-05-17
**Phase**: Shippable — Maestro is now a native binary anyone can download and run
**Branch development name**: v0.0.4 (rolled up under v0.1.0 at release)

This is the first release a non-developer can actually use: download a single-file
binary from GitHub Releases, run `maestro install`, restart Claude Code, see 6
worker tools in `/mcp`. Three Epics shipped on this branch.

| Epic | Focus | Closed |
| --- | --- | --- |
| Epic 8 (#78) | Workflow tooling — `verifier` + `spec-writer` roles, `librarian` `file_paths` mode, generic `scribe` schema, contract-sheets playbook | 2026-05-17 |
| Epic 9 (#88) | Web UI all-pages redesign (Dashboard Cockpit) | 2026-05-16 |
| Epic 10 (#105) | Native binary distribution (cc-switch-style ship form) | 2026-05-17 |

### Epic 10 — Native binary distribution (closed 2026-05-17)

The release-form transformation. v0.0.3 shipped as a git-clone + venv flow that
was only realistic for developers. v0.1.0 ships as a 19MB single-file PyInstaller
binary per OS that anyone can download, place on PATH, and register with Claude
Code in one command.

What shipped (6 sub-tasks):

- **T10.1 (#106)** — CLI integration. `bootstrap/maestro_server.py` (2.5k LOC)
  relocated to `maestro/mcp_server.py`. New `maestro` console-script with
  subcommands `serve` / `webui` / `install` / `--version`. `pyproject.toml`
  bumped 0.0.3 → 0.0.4 (→ 0.1.0 at release).
- **T10.2 (#107)** — PyInstaller spec. `pyinstaller.spec` bundles entry +
  webui templates/static + scaffold templates + hidden-imports for
  uvicorn/pydantic/mcp/openai. `scripts/build-binary.sh` creates a clean
  build venv and verifies. `docs/ops/binary-build.md` operator doc.
  Local build produces `dist/maestro` at 19MB on macOS arm64.
- **T10.3 (#108)** — GitHub Actions release matrix. Push of `v*` tag triggers
  cross-OS build (macOS / Linux / Windows), uploads tarballs/zips to a new
  GitHub Release. `workflow_dispatch` escape hatch for dry-run.
- **T10.4 (#109)** — `maestro install` real implementation. Writes /
  updates `~/.claude/mcp.json` with the maestro entry pointing at the
  binary. Flags: `--force`, `--dry-run`, `--config-path`. Idempotent;
  refuses to overwrite malformed existing JSON; preserves non-maestro
  entries verbatim.
- **T10.5 (#110)** — README install section rewritten (H3-protected own PR).
  Per-OS download table, macOS Gatekeeper bypass, `maestro install` flow,
  `/mcp` verify, upgrade pointer to `docs/ops/mcp-reload.md`.
- **T10.6 (#111)** — `scripts/smoke-fresh-install.sh` end-to-end smoke
  + post-release `verify` job in the release workflow. Tests:
  download → extract → version → install → mcp.json correctness →
  idempotency → MCP `tools/list` handshake returns all 6 worker tools.
  **Local validation PASS** against the T10.2 build artifact.

### Epic 8 — Workflow tooling (closed 2026-05-17)

The orchestrator-side tooling Epic. Added the missing roles that the
orchestrator was previously hand-doing.

- **T8.1 (#79)** — `librarian` `file_paths: list[str]` multi-file mode.
  Three-way XOR: `file_path` / `file_paths` / `document_text`.
- **T8.2 (#80)** — `verifier` role for fact-checking spec → output drift.
  `SHIPPED_TOOL_IDS` framework split (team-configurable roles vs
  shipped-only infrastructure tools); `RoleId` Literal extended;
  `TeamConfig` unchanged for backward compat.
- **T8.3 (#81)** — `spec-writer` role. Mirrors verifier shape via the
  same `SHIPPED_TOOL_IDS` extension.
- **T8.4 (#82)** — `docs/playbook/contract-sheets.md` playbook (6
  sections incl. shadow-mode trial protocol with 4 phases).
- **T8.6 (#83)** — out-of-repo memory updates: size-carve-out
  exception + contract-sheet-reference exception.
- **T8.7 (#74 / #84)** — `CLAUDE.md` sanitization (trial wave used all
  three new tools end-to-end — spec_writer + coder + verifier +
  reviewer + scribe).
- **T8.8 (#85)** — scribe schema generic-ification. Required input
  shrunk from `{diff, issue_number, issue_title, issue_body,
  convention}` to `{diff, purpose}`. Adds `style` enum and
  `audience_context`. Folds #72.

### Epic 9 — Web UI all-pages redesign (closed 2026-05-16)

Replaced the placeholder landing page and the eight pages of per-page
inline CSS that had accumulated through Epics 0–7 with a unified
**Dashboard Cockpit** design language, all eight pages now extending a
single `_base.html` and styled from a single `maestro.css`.

What shipped:

- **ADR-0012** — locks the design tokens (palette, typography, spacing,
  layout primitives, no-build stance).
- **`docs/design/88-webui-redesign.md`** — 640-line design doc with
  per-page wireframes, data sources, and component vocabulary.
- **`_base.html`** — shared Jinja2 base with 220px sidebar + 7-link nav
  + main content slot. Exposes `title`, `extra_head`, `content`,
  `extra_scripts`, `nav_active` blocks.
- **`maestro/webui/static/maestro.css`** — 550-line single static
  stylesheet: tokens on `:root`, reset, sidebar layout, page header,
  KPI strip, panel, entry tile, now-running, badges (8 variants),
  forms, buttons (4 variants), empty state, data-table (+dense
  variant), responsive floor.
- **`GET /api/overview`** — new endpoint aggregating today's dispatches +
  cumulative savings + active workers + open problems + 7-day sparkline
  + now-running snapshot. Reads typed events from
  `.maestro/logs/dispatch.jsonl` and cost rows from
  `savings.resolve_log_path()` (two distinct files per project
  convention).
- **All 8 user-facing pages redesigned**: `/` (Overview), `/team`
  (catalog + edit), `/wizard` (4 steps + field-error), `/scaffold`
  (picker + plan + plan-row + apply), `/live`, `/history`, `/savings`
  (+ empty / disabled / error), `/problems`.
- Page-specific `<style>` exceptions allowed in `extra_head` for
  unique components (wizard-progress, live's legacy class names,
  history drill-down, problem-row variants) per design doc §5.3.
- Sidebar nav `/team-catalog` route bug caught and fixed during T9.11
  real-data smoke (actual route is `/team`).

Per-task economics in `docs/data/dispatch-log.jsonl`; refresh
`docs/savings.md` for the post-Epic-9 totals.

### AI contributors (Epic 9)

- **claude-opus** (orchestrator) — design doc + ADR-0012 + coder
  specs + spec-fix iterations + journal.
- **deepseek-v4-pro** — coder for T9.1, T9.2, T9.3, T9.4, T9.5, T9.6,
  T9.7, T9.8, T9.9, T9.10.
- **deepseek-v4-flash** — librarian (4 calls for T9.2 upstream contracts),
  scribe (commit messages).
- **deepseek-v4-pro** — reviewer (10 passes + 1 fail + retry on T9.8).

### Lessons learned (Epic 9)

1. **Real-data smoke catches what structural tests miss.** All 8
   redesign tests asserted the same nav link `/team-catalog`, which was
   wrong (route prefix is `/team`). Internal consistency hid the bug;
   `curl`-ing all 11 routes end-to-end after the merge surfaced it
   immediately. Pattern: full-route smoke is non-redundant with
   per-template assertions when the template depends on a route the
   test doesn't actually hit.

2. **Synthetic test fixtures must replicate the production data
   layout.** T9.2's `/api/overview` happy-path test wrote events to the
   same file the test patched `resolve_log_path` to point at, masking
   the fact that production has two separate files (typed events vs
   cost rows). Bug only surfaced when running against the real on-disk
   files. Going forward: when synthesizing fixtures, mirror the
   production layout (multi-file, distinct shapes) — don't collapse to
   the simplest model.

3. **Page-specific `<style>` blocks are fine in moderation.** Wizard
   progress dots, live's legacy card markup, history drill-down,
   problem-row variants — each landed as ONE `<style>` block in
   `extra_head`, justified by comment citing design doc §5.3. The
   alternative (~30 single-use shared classes) was rejected. The
   `<style>`-exception pattern is now established convention.

4. **Coder empty-output requires manual re-dispatch (today).** T9.4's
   first dispatch returned 97s of wall and 5.5k tokens with no body —
   just the banner. Re-dispatched same spec verbatim, got correct
   output 56s later. No protocol-level retry exists in the worker
   infrastructure yet. Tracked as a v0.0.5 nice-to-have.

5. **Wave-of-4-parallel works for file-disjoint redesigns.** Both
   batches of Wave 2 (T9.3–T9.6 and T9.7–T9.10) dispatched 4 coders
   simultaneously. Every coder output was file-disjoint from the other
   three; merge order didn't matter. The orchestrator's per-task
   spec-write + post-coder reviewer dispatch was the throughput
   bottleneck, not the coders themselves.

6. **One reviewer fail across 10 reviewer passes.** T9.8 was the only
   fail (inline-style strictness on drill-down). Fix + re-review took
   ~1 min. The other 9 passes had at most low-severity findings (Jinja
   strict-undefined, one inline `font-size: 12px`) — none blocked
   merge. This suggests the design doc + base template were stable
   enough that parallel-dispatched coders mostly produced specifically
   on-target output.

7. **The wrong-URL bug shows the limit of internal test consistency.**
   T9.1's spec hard-coded `/team-catalog` in the base template AND in
   every redesign test that checked nav links. Eight subsequent coder
   dispatches inherited the wrong URL via the design doc that cited
   the base template. The full pytest suite stayed green throughout
   the Epic until the very last task's real-data smoke. Reinforces:
   tests written against a spec cannot validate the spec itself.
