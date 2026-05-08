# ADR-0007: Dispatch log — JSONL format, event schema, concurrency

**Status**: accepted
**Date**: 2026-05-08
**Issue**: #15

## Context

Epic 3 introduces dispatch observability — a log of every worker
invocation that the MCP server makes (today: `cheap_code_gen` only;
post-v0.0.3: more workers). The log is consumed by the Web UI for the
history view, the live execution-flow view, and the problem panel.

Three concerns drive this ADR:

1. **Storage format.** File-based (JSONL) vs database-based (SQLite)
   vs other. Affects every downstream choice — atomicity, queryability,
   tail mode, debuggability, packaging.
2. **Event schema.** What event types exist, what fields each carries,
   how schema migration works across Maestro releases. Epic 1 D4
   already named two new event types
   (`dispatch.fallback.config_absent`, `dispatch.refused.config_invalid`)
   that this schema must accommodate.
3. **Concurrency.** Two MCP server processes can run simultaneously
   (user with two Claude Code sessions on the same project). Both
   append to the same log. Without an atomicity guarantee, lines tear.

[ADR-0003](0003-shared-state-file-layout.md) already pinned the path
(`<project-root>/.maestro/logs/dispatch.<format>`). This ADR settles
the format and what's inside.

## Decision

### Format: JSONL — append-only file at `.maestro/logs/dispatch.jsonl`

One JSON object per line, terminated by `\n`. Append-only — events are
never updated or deleted in place; rotation happens via file
replacement.

### Schema — common fields plus event-type-specific payload

Every event carries:

```json
{
  "event_type": "dispatch.start",
  "event_version": 1,
  "request_id": "01HXNZ7K0K3M7VHV6E5G6X4XYA",
  "timestamp": "2026-05-08T14:23:11.123Z"
}
```

- `event_type` — namespaced string under `dispatch.*`. The reader
  switches on it to pick the deserialization shape.
- `event_version` — integer, **per event type**. Allows adding fields
  to one event type without bumping a global schema version. Old
  readers that encounter an unknown version log a warning and skip the
  event; new readers handle multiple versions.
- `request_id` — UUID per dispatch (ULID-style for sortability is
  fine). Correlates `start` / `end` / `failed` and any pre-start
  informational events.
- `timestamp` — ISO 8601 with timezone, always UTC `Z`.

### Event types — five for v0.0.3

| Type | Role in flow | Type-specific fields |
|---|---|---|
| `dispatch.fallback.config_absent` | Pre-start informational; emitted when `team.yaml` absent and MCP falls back to v0.0.2 default | `role`, `fallback_model` |
| `dispatch.refused.config_invalid` | Terminal-by-itself; refused dispatch, no `start`/`end` pair follows | `validation_error_field`, `validation_error_message` |
| `dispatch.start` | Worker invocation begins (always, including fallback path) | `role`, `model`, `member`, `input_summary` |
| `dispatch.end` | Worker invocation completes successfully | `output_summary`, `duration_ms`, optional `cost` (`{ prompt_tokens, completion_tokens, usd? }`) |
| `dispatch.failed` | Worker invocation fails | `duration_ms`, `error_kind`, `error_message` |

#### Event flows

- **Happy path with config**: `dispatch.start` → `dispatch.end`.
- **Happy path with config-absent fallback**:
  `dispatch.fallback.config_absent` → `dispatch.start` (with
  `model = fallback_model`) → `dispatch.end`.
- **Failure path**: `dispatch.start` → `dispatch.failed`.
- **Refused path**: `dispatch.refused.config_invalid` (single terminal
  event; no `start`/`end`).

`dispatch.start` always carries the model actually being invoked,
whether from `team.yaml` or fallback. The Web UI determines from the
preceding `fallback.config_absent` event (if any) whether the model
came from config or fallback.

#### Deferred event types

- **`dispatch.blocked`** ("worker needs human input") — deferred.
  Shipping it requires worker behavior change; v0.0.3's worker is the
  v0.0.2 `cheap_code_gen` unchanged. Re-open when richer workers
  arrive (v0.0.4+).

### In-code contract: Pydantic discriminated union

```python
class DispatchStartEvent(BaseModel):
    event_type: Literal["dispatch.start"] = "dispatch.start"
    event_version: int = 1
    request_id: str
    timestamp: datetime
    role: RoleId
    model: str
    member: str
    input_summary: str

# similar models for end, failed, fallback.config_absent, refused.config_invalid

DispatchEvent = Annotated[
    Union[
        DispatchStartEvent,
        DispatchEndEvent,
        DispatchFailedEvent,
        DispatchFallbackConfigAbsentEvent,
        DispatchRefusedConfigInvalidEvent,
    ],
    Field(discriminator="event_type"),
]
```

MCP server emits via `event.model_dump_json()`. Web UI reads via
`pydantic.parse_raw_as(DispatchEvent, line)`. Same Pydantic discipline
as `team.yaml` ([ADR-0004](0004-team-config-format-and-schema.md)).

### Per-event size cap: 4 KB

The serialized line (including trailing `\n`) must be under **4096
bytes**. This is what makes the concurrency guarantee below hold.

D3 (Epic 3 pass-2) settles truncation rules for `input_summary`,
`output_summary`, and `error_message` to enforce this cap.

### Concurrency

Two MCP server processes may run simultaneously and both append to
`dispatch.jsonl`. The atomicity story:

#### POSIX (Linux, macOS)

Files opened with `O_APPEND` and written via a single `write()` syscall
of size less than `PIPE_BUF` are atomic across processes — the kernel
guarantees no interleaving of partial writes. `PIPE_BUF` is at least
512 (POSIX minimum), in practice 4096 on Linux and macOS.

Implementation:

```python
fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
os.write(fd, line.encode("utf-8") + b"\n")
```

One `os.write()` per event. With the 4 KB size cap, two concurrent
writers can never tear each other's events.

#### Windows

`O_APPEND` atomicity guarantees on Windows differ from POSIX. v0.0.3
ships Linux/macOS-correct; Windows users either run WSL or accept
best-effort atomicity (in practice fine for single-user; pathological
only under high concurrency, which v0.0.3 doesn't generate).

Documented as a known caveat; revisit if Windows becomes a primary
target.

#### Reader side

The Web UI is single-process. Multiple browser tabs share one
tail-reader. Read path:

- Track last-read offset in memory.
- On poll (default 1 Hz): `os.stat(path)`, if size > offset, read new
  bytes, split on `\n`, parse complete lines, update offset.
- Inotify/kqueue is a future optimization.

#### File rotation

D3 settles retention. The format-side contract: rotation happens via
file replacement — old file renamed to `dispatch.<timestamp>.jsonl`,
new empty `dispatch.jsonl` created. Readers track the file's **inode**
in addition to the offset; when the inode changes, reopen and reset
offset to 0.

## Alternatives considered

- **SQLite** — rejected. Indexed queries are tempting but unneeded at
  v0.0.3 scale (hundreds-to-low-thousands of events per project,
  scannable in <100ms in Python). SQLite adds locking complexity, a
  binary-file debug story (no `tail -f`/`jq`), and a schema-migration
  surface that the per-event `event_version` field on JSONL avoids.
  Backups become "sqlite-aware backup" instead of `cp dispatch.jsonl
  backup.jsonl`. Not earned.
- **One JSON document per file** (e.g., `dispatch-2026-05-08.json`
  containing an array). Rejected — every append rewrites the whole
  file; not atomic; not concurrent-friendly.
- **Per-process log files** (each MCP process writes its own file) —
  rejected. Adds cross-file ordering as a UI concern, multiplies file
  count without benefit. The append-only single-file approach handles
  concurrency at the kernel.
- **Global file-level `schema_version`** — rejected in favor of
  per-event `event_version`. Per-event versioning lets us add fields
  to one event type without affecting others or forcing a migration
  pass.
- **Including `dispatch.blocked` in v0.0.3** — rejected. Worker-behavior
  change; v0.0.3's worker is unchanged from v0.0.2. Defer to v0.0.4+.
- **MessagePack or other binary format** — rejected. Loses
  human-readability and `jq`-debuggability for marginal size savings.
  4 KB events at JSONL densities are fine on disk.

## Consequences

### Good

- **JSONL is the simplest format that solves the problem.** One file,
  append-only, line-oriented. Tools like `tail`, `head`, `jq`, `grep`
  work out of the box.
- **POSIX `O_APPEND` gives free atomicity** for events under
  `PIPE_BUF`. No locks, no WAL, no transaction machinery. Two
  concurrent MCP processes coexist by kernel guarantee.
- **Per-event `event_version`** keeps schema migration granular —
  adding a field to `dispatch.end` doesn't force a rewrite of all
  existing events. Old readers see new fields they don't know about
  and skip them; new readers handle multiple versions.
- **Pydantic discriminated union** gives one in-code contract that
  serves emission (MCP) and consumption (Web UI). Reuses the same
  pattern as `team.yaml`.
- **Debuggability**: a developer hitting a bug can `tail -f
  .maestro/logs/dispatch.jsonl | jq` and see what's happening.
  Compare to opening a SQLite browser.
- **Easy backup, easy gitignore.** `.maestro/.gitignore` already
  excludes `logs/`; no further work.

### Bad / risks

- **No indexed queries.** A history view that wants "show me all
  failures last week" must scan. At v0.0.3 scale this is fine; at
  10⁶+ events per project it isn't. Mitigation: rotation (D3) keeps
  the active file small. If history grows beyond JSONL's comfort,
  v0.x.0 can index by introducing a sidecar SQLite cache without
  changing the on-disk truth.
- **4 KB per-event cap is restrictive.** A `cheap_code_gen` invocation
  with a long prompt or a long response will be truncated for
  logging. Mitigation: D3 specifies truncation as "first/last N chars
  with an ellipsis"; the full payload is still seen by Claude Code at
  dispatch time — only the *log entry* is truncated.
- **Windows atomicity is best-effort.** Pathological concurrent writes
  could tear lines on Windows. Mitigation: documented; v0.0.3's
  primary target is Linux/macOS; the worst-case is one corrupted log
  line, which the reader detects (parse failure → log warning → skip
  line) without breaking dispatch.
- **Per-event `event_version` adds reader complexity.** Each event
  type needs version-aware parsing in the long run. v0.0.3 ships
  every event at version 1, so this cost is deferred. When the first
  event type hits version 2, we pay it.
- **No update-in-place** means computed-after-the-fact data (cost
  numbers that arrive late from a provider's billing API, e.g.) goes
  in the *next* event or doesn't go at all. v0.0.3 puts cost in
  `dispatch.end` and accepts that some providers won't surface it
  until later (in which case `cost` is just absent for that event).

### Reversibility

- **Format choice (JSONL): hard.** Switching to SQLite later means
  a one-time migration of all user logs. Doable; not free. Treat the
  format as durable for v0.0.x.
- **Schema additions (new fields, new event types): easy.** Per-event
  `event_version` and the discriminated union were designed for this.
- **Schema removals (dropping a field): hard.** Old logs still have
  the field; readers must accept-and-ignore. Plan removals as
  "deprecate, ignore, migrate" cycles.
- **Concurrency model (`O_APPEND` atomicity): foundational.** Changing
  it (to e.g. process-local files, or a mediated single writer) is a
  bigger architectural shift. Treat as locked.
