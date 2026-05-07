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

## v0.0.2 — TBD (first self-hosted feature)

This will be the first version where Maestro is used to develop Maestro. Every commit from here on must include `Co-authored-by` attribution for any AI model that contributed substantive code.
