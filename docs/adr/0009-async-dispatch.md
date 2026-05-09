# ADR-0009: Async dispatch via enqueue + poll

**Status**: accepted
**Date**: 2026-05-09
**Issue**: #55

## Context

T5.2 verification revealed that Claude Code's MCP request timeout is
hard-coded at approximately 60 seconds and is not configurable. The
documented `MCP_TIMEOUT` environment variable governs server *startup*
only; the `timeout` field in `mcpServers` config entries is silently
ignored. This is a known issue (anthropics/claude-code#3033, #43791).

For Maestro, this constrains every dispatched worker call to <60s
end-to-end. In practice that means:

- `coder` on `deepseek-v4-pro` for detailed specs (~150 lines) reliably
  exceeds the limit. Both T5.2 dispatches (reviewer + scribe) timed out
  client-side, even though the server kept processing.
- Dogfooding's command — worker-by-default for mechanical work — fails
  on exactly the cases where dispatching matters most: substantive
  specs that earn their token savings.

Without a fix, the orchestrator silently falls back to writing code
itself whenever the worker takes too long. The whole project's
self-hosting thesis degrades.

## Decision

Adopt an **enqueue + poll** dispatch pattern for every worker tool.

### Pattern

1. Tool call (e.g., `coder(spec, language)`) registers a job with a UUID,
   fires off the actual work as `asyncio.create_task`, and returns
   `{"job_id": "<uuid>"}` immediately.
2. The MCP server exposes a `job_status(job_id)` tool. Each call looks up
   the in-memory job dict and returns one of:
   - `{"status": "running", "tool": <role>}` — worker is still in flight.
   - `{"status": "done", "tool": <role>, "result_text": "..."}` — work
     completed; `result_text` carries exactly what the underlying handler
     would have returned synchronously.
   - `{"status": "failed", "tool": <role>, "error": "..."}` — worker
     raised an exception or returned a server-side error.
3. Caller (orchestrator) polls `job_status` every ~2 seconds until a
   terminal state. Each MCP call (enqueue + each poll) returns in <1
   second, so the 60s ceiling is no longer in the critical path.

### State

Job records live in a process-local Python dict keyed by UUID. Each
record carries: `job_id`, `tool`, `status`, `result_text` (on done),
`error` (on failed), `created_at`, `completed_at`. State is **not
persisted** across server restarts — the bootstrap MCP server is
throwaway-tier and a restart-during-job is rare in practice. If it
happens, the orchestrator's poll returns `job_not_found` and the
caller decides whether to retry the original call.

### Result-content shape

The `result_text` field carries the underlying handler's TextContent
text verbatim. This is a string — JSON in librarian's / reviewer's /
scribe's case, formatted text in coder's. The caller parses based on
which tool was originally called. The async layer doesn't try to
unify the role-specific output shapes; it just transports them.

### What this ADR does NOT decide

- **Job cancellation API.** Caller can stop polling, but the worker
  continues to completion (or natural failure). v0.0.3 does not allow
  the orchestrator to abort a worker mid-flight.
- **Result TTL / GC.** Completed jobs accumulate in memory until
  process restart. Acceptable for v0.0.3's bootstrap-tier server.
- **Persistent job storage.** Out of scope — Epic 4 packaging may
  revisit if v0.x.0+ users hit it in practice.
- **Multi-orchestrator coordination.** v0.0.3 is single-client (one
  Claude Code session at a time). If multiple clients become a thing,
  job ownership semantics need rework.

## Alternatives considered

- **Wait for Claude Code's MCP timeout to become configurable.**
  Rejected: open issues exist but no timeline. Maestro can't depend on
  upstream fixes for its own infrastructure.
- **Stream tokens via MCP's streaming response.** Rejected for v0.0.3:
  MCP's streaming support is uneven across clients and would require
  significant protocol-level work for marginal benefit (the caller still
  has to wait for the complete result to act on it).
- **Long-running synchronous tool with periodic empty responses to keep
  the connection alive.** Rejected: hacky, fights MCP's request/response
  model, and not all MCP clients tolerate this pattern.
- **Persistent job-state file (JSONL or SQLite).** Rejected for v0.0.3
  scope: adds complexity for benefit only realized when servers restart
  during in-flight jobs — rare in current usage. Trigger to revisit:
  observed loss of substantive work due to restart.
- **Status response includes structured `result` (parsed JSON) instead
  of `result_text` string.** Rejected: roles emit different shapes;
  forcing a uniform parse at the async-transport layer pushes role-
  specific logic into infrastructure code. Caller-side parse is cleaner.

## Consequences

### Good

- Removes the 60s ceiling from any worker dispatch. Workers can take
  arbitrarily long (subject to OpenAI client timeout, currently 120s
  but separately configurable per-call if needed).
- All four roles get the upgrade in one refactor — no per-role
  divergence.
- The pattern generalizes: any future role drops in with a thin
  `tool → enqueue → background impl` shim.
- Status polling is cheap and idempotent. Caller can re-poll
  arbitrarily without side effects.

### Bad / risks

- **Two-call protocol replaces one-call.** Caller (orchestrator)
  becomes responsible for the polling loop. We document the pattern
  in user memory so cold-start sessions follow it.
- **In-memory state is fragile.** Server restart loses in-flight
  jobs. Recoverable (caller retries) but is a UX bump if it happens
  during a long task.
- **Memory accumulation.** Old job records linger until restart. For
  v0.0.3 single-user scale (~dozens of jobs/day), this is bounded.
- **Polling overhead.** ~2s polling adds a few seconds of latency on
  short jobs (small spec → coder finishes in 5s but caller polls
  twice). Acceptable; cheaper than a 60s timeout.

### Reversibility

**Medium.** The protocol shape (enqueue + poll) is durable across the
project and embedded in the orchestrator's calling pattern. Reverting
to synchronous would require unwiring the polling logic and either
finding a Claude Code timeout fix (still needs upstream) or accepting
the 60s ceiling (regresses dogfooding). Implementation details (in-
memory dict vs. file vs. SQLite) are easily swappable.

## Sibling open questions resolved

- T5.2-derived OPEN: how to handle dispatches whose duration exceeds
  Claude Code's MCP timeout. Resolved by this ADR.
