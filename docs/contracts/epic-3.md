# Epic 3 — shared contract sheet

Single source of truth for Epic 3 (observability) upstream contracts.
**Caller**: any task within Epic 3 (T3.7–T3.10 and beyond) that depends
on the dispatch-log data model, reader, writer, dispatcher, or SSE
endpoint. Spec authors paste relevant sections verbatim into coder /
reviewer payloads — avoids the W5 mistake of re-discovering contracts
per task.

**Format convention**: every entry is verbatim from the production
code. When the source changes, update this sheet in the same PR.

---

## 1. Event models (`maestro/dispatch_log/events.py`)

Pydantic discriminated union on `event_type`. 5 event types in v0.0.3.

### Common base (every event)

```python
class _DispatchEventBase(BaseModel):
    """Fields shared by all dispatch events."""
    event_version: int = Field(default=1)
    request_id: str
    timestamp: datetime
```

JSON serialization: `event.model_dump_json()` produces ISO 8601 string
for `timestamp`; UI parses back via `DISPATCH_EVENT_ADAPTER.validate_json()`.

### `dispatch.start` — worker invocation begins

```python
class DispatchStartEvent(_DispatchEventBase):
    event_type: Literal["dispatch.start"] = "dispatch.start"
    role: RoleId
    model: str
    member: str
    input_summary: str
```

### `dispatch.end` — worker invocation succeeds

```python
class DispatchEndEvent(_DispatchEventBase):
    event_type: Literal["dispatch.end"] = "dispatch.end"
    output_summary: str
    duration_ms: int
    cost: Optional[CostBreakdown] = None
```

### `dispatch.failed` — worker invocation fails

```python
class DispatchFailedEvent(_DispatchEventBase):
    event_type: Literal["dispatch.failed"] = "dispatch.failed"
    duration_ms: int
    error_kind: str
    error_message: str
```

### `dispatch.fallback.config_absent` — pre-start info (Epic 1 D4)

```python
class DispatchFallbackConfigAbsentEvent(_DispatchEventBase):
    event_type: Literal["dispatch.fallback.config_absent"] = "dispatch.fallback.config_absent"
    role: RoleId
    fallback_model: str
```

### `dispatch.refused.config_invalid` — terminal alone (Epic 1 D4)

```python
class DispatchRefusedConfigInvalidEvent(_DispatchEventBase):
    event_type: Literal["dispatch.refused.config_invalid"] = "dispatch.refused.config_invalid"
    validation_error_field: str
    validation_error_message: str
```

### Cost breakdown

```python
class CostBreakdown(BaseModel):
    """Token usage and optional USD cost for a dispatch call."""
    prompt_tokens: int
    completion_tokens: int
    usd: Optional[float] = None
```

### Union alias + TypeAdapter

```python
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

DISPATCH_EVENT_ADAPTER = TypeAdapter(DispatchEvent)
```

### `RoleId` Literal — **must enumerate**

```python
RoleId = Literal["coder", "librarian", "reviewer", "scribe"]
```

W5 pitfall: any test that constructs an event with `role="junior"` /
`"senior"` / `"editor"` etc. **silently fails Pydantic validation**.
Always use one of the four enumerated strings.

---

## 2. Reader (`maestro/dispatch_log/reader.py`)

### `scan_log` — one-shot, no tail

```python
def scan_log(path: Path) -> list[DispatchEvent]:
    """Return all events in insertion order; skip unparseable lines with a warning.

    Missing file is treated as no-events-yet (returns []) so the UI can
    load before any dispatch has happened."""
```

**Failure contract**:
- Missing file → returns `[]` (does NOT raise)
- Unparseable JSON line → skipped + `RuntimeWarning` (does NOT raise)
- Unreadable existing file (permission error) → propagates `PermissionError`

Import: `from maestro.dispatch_log.reader import scan_log`

### `tail_log` — generator, polling-based

```python
def tail_log(
    path: Path,
    start_offset: int = 0,
    poll_interval: float = 1.0,
    stop_event: threading.Event | None = None,
) -> Iterator[tuple[int, int, DispatchEvent]]:
    """Yield (inode, byte_offset, event) tuples as new events append.

    Polls os.stat at poll_interval. Detects rotation via inode change.
    Partial trailing line held in memory until newline arrives."""
```

Used by T3.6 SSE endpoint to bridge sync polling to async generator.

---

## 3. Writer (`maestro/dispatch_log/writer.py`)

```python
def emit_event(event: DispatchEvent, project_root: Path | None = None) -> None:
    """Append the event as JSONL to <project_root>/.maestro/logs/dispatch.jsonl.

    POSIX O_APPEND ensures atomic concurrent appends from multiple
    processes (each event ≤ 4 KB). Rotation at 5 MB.

    Stderr fallback on OSError: never raises into the caller."""
```

Import: `from maestro.dispatch_log.writer import emit_event`

---

## 4. Paths (`maestro/paths.py`)

### `dispatch_log_path` — returns the LOGS DIRECTORY (not the file)

```python
def dispatch_log_path(project_root: Union[Path, str]) -> Path:
    """Return <project_root>/.maestro/logs/ — directory holding dispatch event log files.

    Note: this returns the logs directory, not a specific file."""
```

**W5 pitfall**: callers always append `/ "dispatch.jsonl"` to get the
active log file. Forgetting this triggers `IsADirectoryError` at read
time.

Standard composition:
```python
log_file: Path = paths.dispatch_log_path(Path.cwd()) / "dispatch.jsonl"
```

Used identically in `dispatch_log/writer.py`, `webui/dispatch_log_api.py`,
`webui/history_view.py`, `webui/problem_panel.py`.

---

## 5. Dispatcher (`maestro/dispatcher.py`)

```python
async def run(
    role: str,
    payload: str,
    executor: Callable[[str], Awaitable[str]],
    emit_event: Callable[[DispatchEvent], None] = default_emit_event,
) -> str:
    """Resolve role → model (per Epic 1 D4), emit start/end/failed
    events, invoke executor, return result or refusal string."""
```

3-state branching delegated to `maestro.team.resolve.resolve_role_model`:
- Valid config → start + executor + end (success path)
- Config absent → fallback event + run with DEFAULT_MODELS[role]
- Config invalid → refused event + return error string

**Refusal detection (caller side, fragile)**: dispatcher returns `str`;
refusals are detected via `result.startswith("team.yaml at")`.
v0.0.4 candidate: typed dispatcher result (T3.5b/T3.5c reviewers
flagged this; see `docs/journal/2026-05-12-epic3-w1-to-w4.md` deferred).

---

## 6. SSE endpoint (`maestro/webui/dispatch_log_api.py`)

### Route

```python
@router.get("/api/dispatch_log/stream")
async def stream_dispatch_log(request: Request) -> EventSourceResponse:
```

### Event ID format

`<inode>:<byte_offset>` — each yielded event carries an `id:` line.
Client's browser-native `EventSource` auto-sends `Last-Event-ID` on
reconnect; server parses via `_parse_last_event_id` and resumes.

### Event types yielded

- **Default** (no `event:` line): `data:` = full JSON of one of the 5
  dispatch event models.
- **`event: rotated`**: empty `data:`. Emitted when the underlying
  file's inode changes (rotation). Client should clear any open
  Running state and continue.

### Cold start vs reconnect

- Cold start (no `Last-Event-ID`): emit all events from offset 0.
- Reconnect with `Last-Event-ID = <inode>:<offset>`:
  - Same inode → resume from offset.
  - Different inode → emit `rotated` event first, then continue from
    offset 0 of the new file.

---

## 7. Shared UI conventions (Epic 3 Surfaces 1-3, D6 language rule)

### Browser tab title pattern (cross-page)

**Convention**: `<title>Maestro · 中文页面名</title>` (Maestro first,
middle dot, Chinese after). Matches `index.html` precedent.

- ❌ `<title>调度历史 — Maestro</title>` — order reversed; flagged by
  W-level reviewer 2026-05-12.
- ✅ `<title>Maestro · 调度历史</title>`

### Status icons + labels

| event_type | icon | Chinese label |
|---|---|---|
| `dispatch.end` | `✓` | 成功 |
| `dispatch.failed` | `✗` | 失败 |
| `dispatch.refused.config_invalid` | `⊘` | 已拒绝 |
| `dispatch.fallback.config_absent` (alone) | `↩` | 已降级 |
| `dispatch.fallback.config_absent` (paired with start) | badge `↩ 已降级` | (attached to row) |
| `dispatch.start` (no terminal yet) | `◐` | 进行中 |

### Duration formatting

```
≥ 1000 ms → "{seconds:.1f} 秒"
<  1000 ms → "{ms} 毫秒"
None      → "—"
```

Python (history view): `_format_duration` in `history_view.py`.
JS (live view): `formatElapsed` in `live.html` — must stay synchronized.

### Cost formatting

```
present  → "{prompt_tokens}→{completion_tokens} tok"
None    → "—"
```

### Time formatting

```
HH:MM:SS  in row (local time)
ISO 8601  in hover title (via datetime.isoformat() — preserves tz offset,
                          NOT hardcoded Z)
```

### CTA targets (problem panel)

| source event | CTA label | route |
|---|---|---|
| `dispatch.refused.config_invalid` | 打开团队配置修复 | `/team` (Epic 1 T1.5) |
| `dispatch.fallback.config_absent` (grouped) | 配置团队 | `/wizard` (Epic 1 T1.4) |

### Truncation marker

Row summary truncated at 60 chars → drill-down dl shows `（已截断）`
annotation alongside full text.

---

## 8. Templates name-collision gotcha

`maestro.webui.templates` is BOTH:
- An attribute on the package: the `Jinja2Templates(...)` instance in `__init__.py`
- A subdirectory: `maestro/webui/templates/` holding `*.html` files

During pytest collection, the subdirectory may be registered as a
namespace package in `sys.modules['maestro.webui.templates']`,
shadowing the attribute. Symptoms: `AttributeError: module 'maestro.webui.templates' has no attribute 'TemplateResponse'`.

**Workaround**: late-bind import inside view functions:

```python
@router.get("/X", response_class=HTMLResponse)
async def view(request: Request):
    from maestro.webui import templates  # late-bind
    return templates.TemplateResponse(request, "X.html", {...})
```

Module-top import (e.g., `from maestro.webui import templates`) only
works if no other test has triggered the namespace-package registration
first.

Permanent fix candidate: rename the directory (e.g.,
`maestro/webui/jinja/`) — out of scope for v0.0.3.

---

## 9. Test conventions

### Fresh app fixture (Epic 3 default)

```python
@pytest.fixture
def app():
    application = FastAPI()
    application.include_router(<the_view_router>)
    return application

@pytest.fixture
def client(app):
    return TestClient(app)
```

Avoids depending on production app wiring (`maestro.webui.app`) — keeps
tests independent of `__init__.py` state and order-of-imports.

### Mock `Path.cwd()`

```python
@pytest.fixture
def mock_cwd(tmp_path, monkeypatch):
    (tmp_path / ".maestro" / "logs").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
    return tmp_path
```

Note: `tests/conftest.py` has an autouse `subprocess.run` patch
(`feedback_conftest_subprocess_patch_trap`). If a test needs real
subprocess, capture `_REAL_SUBPROCESS_RUN` at module top before the
fixture activates.

---

## 10. Deferred to v0.0.4

- **Typed dispatcher result** — replace `str`-based refusal detection
  with structured return (T3.5b/T3.5c reviewers flagged).
- **SSE streaming tests** (T3.6) — 2 `@pytest.mark.skip` tests pending
  httpx async client refactor or alternate test harness.
- **Templates name-collision** — rename `maestro/webui/templates/` to
  `maestro/webui/jinja/` to eliminate late-bind requirement.
- **Older log files in history view** — currently only reads the
  active `dispatch.jsonl`; rotated `dispatch.<ts>.jsonl` files exist
  on disk but aren't loaded.
- **Cross-session ack persistence** in problem panel — out of v0.0.3
  scope by design.

---

## Update protocol

- Modify code → modify this sheet in the **same PR**.
- New event type / new shared label → append section here + reference
  in commit.
- Memory entry `feedback_verify_paths_before_spec` continues to apply:
  this sheet is the canonical reference, but spec authors must still
  re-grep before writing to confirm.

Last updated: 2026-05-12 (W5 close).
