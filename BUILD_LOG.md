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
