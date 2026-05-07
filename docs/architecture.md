# Maestro Architecture Principles

This document defines the architectural rules that govern *what* gets built. Every design decision must justify itself against these principles.

For workflow rules, see [`governance.md`](governance.md).

---

## P1. Simplicity beats cleverness

Prefer the boring solution. A 50-line file that everyone understands beats a 500-line abstraction that's "more flexible." Premature abstraction is the leading cause of dead code.

**Concrete rule**: If you can't explain a design choice in two sentences, it's probably wrong.

## P2. One responsibility per module

Every file, class, and function should answer one question: "what does this do?" If the answer needs the word "and," split it.

**Concrete rules**:
- A module that imports from more than 5 other internal modules is suspect
- A function longer than ~50 lines is suspect
- A file longer than ~300 lines is suspect

## P3. Security by default, not by addition

Secrets never enter the repo. Untrusted input is validated at the boundary. Permissions are minimal by default and explicitly granted when needed.

**Concrete rules**:
- API keys live in environment variables only — never in code or committed config
- `.gitignore` blocks `.env`, `*.key`, `credentials*`, `*.pem` — verified before every commit
- All external input (user prompts, model output, MCP arguments) is treated as untrusted: never `eval`, never shell-interpolate without escaping, never trust file paths from input
- Dependencies are pinned (`==` or lock file), never floating

## P4. Observability is not optional

Every dispatch, every model call, every error is logged. If you can't reconstruct what happened from the logs, the system has failed.

**Concrete rule**: Any new tool / dispatch / external call must log inputs, outputs, duration, tokens (if applicable), and errors. Logging code is reviewed with the same rigor as business logic.

## P5. Fail loud, recover gracefully

Errors are surfaced clearly to the orchestrator and to the user. The system never silently swallows a failure. But a single component failure never crashes the whole flow — it returns a structured error and lets the caller decide.

**Concrete rules**:
- All external calls (model APIs, file IO, subprocess) wrapped in try/except with specific exception types
- Errors return structured information (what failed, why, suggested next step) — not just a stack trace
- The MCP server never exits because of a tool failure

## P6. Reversibility over perfection

Prefer designs that can be changed cheaply later. A choice that's wrong but easy to undo is better than one that's "right" but cements assumptions.

**Concrete rules**:
- Avoid abstractions that span > 3 modules until you've seen the pattern repeat 3 times (rule of three)
- Favor explicit over magical — explicit imports over auto-discovery, explicit registration over decorators-with-side-effects
- Public interfaces (MCP tool schemas, config file format) change with deprecation notice, never silently

## P7. Minimal dependencies

Every dependency is a liability: maintenance burden, supply chain risk, install time, version conflicts. Add one only when the alternative is meaningfully worse than writing it ourselves.

**Concrete rules**:
- Standard library first, well-known mature libraries second, niche libraries only with justification
- Each new dependency added in a separate commit with rationale in the commit message
- No dependency without a pinned version
- Adding a dependency that requires a non-Python runtime needs an ADR

## P8. Heterogeneity is the product

Maestro's reason to exist is routing different work to different models. The codebase must reflect this — model providers are pluggable, roles are pluggable, the orchestrator never assumes a specific backend.

**Concrete rules**:
- Hardcoding "deepseek" or "qwen" anywhere in core logic is a smell — use config-driven role definitions
- Provider-specific code lives in clearly named adapters, never in shared modules
- Adding a new provider should require ~50 lines of code, not a refactor

---

## How to apply these

When designing a feature or reviewing a PR, walk down this list:

1. **P1, P2** — is this the simplest thing that works?
2. **P3** — does any input cross a trust boundary unchecked?
3. **P4** — can we reconstruct what happened from logs?
4. **P5** — what happens when this fails? Does the system stay alive?
5. **P6** — if we're wrong, can we undo cheaply?
6. **P7** — did we add dependencies? Justified?
7. **P8** — did we couple to a specific model/provider?

If any answer is "no" or "I'm not sure," that's a design discussion to have before merging.

---

## When principles conflict

They will. Common collisions:

- **P1 vs P8**: a generic provider abstraction is more complex than hardcoding one. → Resolve in favor of P8 (heterogeneity is core to the product); accept the complexity but keep it minimal.
- **P3 vs P5**: strict input validation can cause more failures. → Resolve in favor of P3; design failure modes (P5) to handle validation rejections gracefully.
- **P6 vs P7**: a thin wrapper around a library improves reversibility but adds code. → Resolve case-by-case based on how likely we are to swap the library.

When in doubt, optimize for the project's longevity over short-term velocity.
