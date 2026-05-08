# ADR-0001: Web framework — FastAPI

**Status**: accepted
**Date**: 2026-05-08
**Issue**: #12

## Context

v0.0.3 introduces a localhost Web UI that runs alongside the existing MCP
server (see Epic 0, `docs/design/12-epic0-web-ui-skeleton.md`). The Web UI
process needs an HTTP server. Three downstream requirements shape the
choice:

1. **Server-push streaming.** Epic 3's live execution-flow view requires
   the server to push dispatch events to the browser as they happen.
   Server-Sent Events (SSE) is the cleanest fit; WebSockets are
   over-specified for a one-direction stream.
2. **Schema-typed I/O.** Epics 1–3 define data shapes (team config,
   dispatch events, scaffolding plans) that flow between the MCP server,
   the Web UI process, and the browser. The MCP Python SDK is
   Pydantic-based; sharing schemas avoids duplication.
3. **Single-user local scope.** No multi-tenant concerns, no auth, no
   horizontal scaling. The framework should add value here, not absorb
   developer attention with concerns we don't have.

## Decision

Use **FastAPI** as the Web UI process's HTTP framework, served by
**uvicorn** (FastAPI's default ASGI server).

`requirements.txt` gains:

- `fastapi`
- `uvicorn`
- `sse-starlette` (added now to lock in the SSE primitive Epic 3 will
  consume; not yet used in Epic 0's empty shell)

## Alternatives considered

- **Flask** — rejected. SSE in Flask is hand-rolled chunked-encoding or
  the `Flask-SSE` extension (which pulls Redis as a runtime dependency).
  Both options burden Epic 3 with avoidable corner-case work. Lacks
  built-in schema validation, so Pydantic would be added anyway —
  paying most of FastAPI's dependency cost without the integration.
- **Starlette (raw)** — rejected. The async / SSE primitives are there,
  but Pydantic integration and request validation aren't. Choosing
  Starlette over FastAPI gives up the integration without saving
  meaningful weight.
- **Quart** — rejected. Flask-API-compatible but async; small ecosystem,
  divergence cost not justified by any concrete advantage over FastAPI
  for this use case.
- **aiohttp, Bottle** — rejected. Either lack the schema-typed-I/O story,
  or are even smaller niches than the above.

## Consequences

### Good

- Native SSE via `sse-starlette` makes Epic 3's live view straightforward.
- Pydantic shared between the MCP server (already Pydantic-based via the
  MCP SDK) and the Web UI eliminates duplicate schema definitions for
  team config and dispatch events.
- Auto-generated OpenAPI docs at `/docs` give free observability of the
  Web UI's own API surface — useful during development and for users
  who want to script Maestro.
- Async-throughout matches the streaming workload (SSE) without
  fighting the framework.

### Bad / risks

- Larger dependency footprint than Flask (`fastapi` + `starlette` +
  `pydantic v2` + `uvicorn` + `sse-starlette`). Acceptable for a
  local-tool ship target; not acceptable for an embedded or
  size-constrained context (we are neither).
- Async/await idioms can trip contributors used to sync Python. Mitigation:
  keep all routes async; do not mix sync handlers; document this in the
  Epic 0 design doc when implementation lands.
- `uvicorn` is the bundled ASGI server, not a configurable choice. If a
  future need (e.g., process management) demands `hypercorn` or another
  ASGI server, this ADR would need an amendment, not a full supersede.

### Reversibility

**Hard, not irreversible.** Replacing FastAPI later means rewriting all
routes, swapping the schema layer, and refactoring Epic 3's SSE
implementation. None of this is impossible; it would simply cost a
multi-week refactor. Treat the choice as durable.
