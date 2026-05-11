## AI team coordination via Maestro

This project uses Maestro to coordinate multiple AI workers. Team
configuration lives in `.maestro/team.yaml`. The roles available are
`coder`, `librarian`, `reviewer`, and `scribe`.

When you (Claude Code, in the Architect role) need to delegate
implementation, code generation, review, or documentation work, dispatch
to a role via the Maestro MCP tools. The role's bound model handles the
work; results flow back to you. Architect — that's you — orchestrates.

Configuration changes happen in the Maestro Web UI (run `maestro-webui`).
Do not hand-edit `.maestro/team.yaml` unless you know what you're doing.
