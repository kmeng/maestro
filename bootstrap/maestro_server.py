#!/usr/bin/env python3
"""
Maestro Bootstrap MCP Server (v0.0.1)

The minimum viable Maestro: a single MCP tool `cheap_code_gen` that routes
code generation tasks to DeepSeek-Coder. Hand-written by Claude Opus.

From v0.0.2 onward, this codebase will be extended using Maestro itself.

Setup:
    pip install mcp openai python-dotenv
    export DEEPSEEK_API_KEY=sk-...

Register with Claude Code:
    claude mcp add maestro -- python /absolute/path/to/maestro_server.py

Verify:
    /mcp  (should show maestro as connected)
"""

import asyncio
import json
import os
import re
import secrets
import subprocess
import sys
import time
import uuid
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional, Union

from openai import AsyncOpenAI
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# ============================================================
# v0.0.3 transition: expose the `maestro/` package on sys.path so
# paths.py and future shared modules are reachable from this
# bootstrap script. The import below is a startup probe — if the
# package layout is broken the MCP server fails loudly here rather
# than when a downstream caller first needs a path. T0.5 will
# replace this shim with proper pyproject.toml-based packaging.
# ============================================================
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from maestro import paths as _maestro_paths  # noqa: E402, F401
from maestro.env_loader import load_credentials  # noqa: E402

# ============================================================
# Configuration
# ============================================================

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_credentials(project_root=_PROJECT_ROOT)

# T1.2 — startup probe. Calling load_team_config here guarantees the
# maestro.team.io module isn't orphaned and surfaces import-time
# breakage early. Result is discarded; T1.6 wires real per-worker
# resolution.
from maestro.team.io import load_team_config as _probe_load_team_config  # noqa: E402

_probe_load_team_config(_PROJECT_ROOT)

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    project_env = _PROJECT_ROOT / ".env"
    user_env = _maestro_paths.credentials_env_path()
    print(
        f"ERROR: DEEPSEEK_API_KEY not set.\n"
        f"  Provide it via one of (highest precedence first):\n"
        f"    1. process env: export DEEPSEEK_API_KEY=sk-...\n"
        f"    2. project file: {project_env}\n"
        f"    3. user file:    {user_env}",
        file=sys.stderr,
    )
    sys.exit(1)

LOG_DIR = Path(os.environ.get("MAESTRO_LOG_DIR", Path.home() / ".maestro" / "logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# Model identifiers — single source of truth for which DeepSeek model
# serves which role. Epic 1 (team.yaml) will let users override these
# per-project; v0.0.3 ships defaults.
#   MODEL_PRO   — judgment-heavy roles (coder, reviewer)
#   MODEL_FLASH — light extraction / drafting (librarian, scribe)
# ============================================================

MODEL_PRO = os.environ.get("MAESTRO_MODEL_PRO", "deepseek-v4-pro")
MODEL_FLASH = os.environ.get("MAESTRO_MODEL_FLASH", "deepseek-v4-flash")

REQUEST_TIMEOUT_SEC = int(os.environ.get("MAESTRO_TIMEOUT_SEC", "120"))

# ============================================================
# Provider client
# ============================================================

deepseek = AsyncOpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com/v1",
    timeout=REQUEST_TIMEOUT_SEC,
)

# ============================================================
# Structured response prompt
#
# We force every worker to return reasoning + output + concerns.
# This is non-negotiable: it's how the orchestrator (and the human)
# can judge whether the cheap model actually understood the task.
# ============================================================

STRUCTURED_RESPONSE_INSTRUCTION = """
Your response MUST follow this exact format, using the XML-style tags below:

<reasoning>
Briefly (under 150 words) explain:
- How you interpreted the spec
- Key implementation decisions you made
- Anything you were unsure about or had to assume
</reasoning>

<output>
The actual code or deliverable. Nothing else inside these tags.
</output>

<concerns>
Things the caller should verify before using this output. If you're confident
in everything, write "none". Be honest — flagging concerns helps the team.
</concerns>
"""

# ============================================================
# Logging
# ============================================================

def log_dispatch(record: dict) -> None:
    """Append a single dispatch record to today's JSONL log file."""
    log_file = LOG_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        # Logging must never break the main flow
        print(f"[maestro] log write failed: {e}", file=sys.stderr)


# ============================================================
# Dispatch telemetry (Epic 6 / T6.2)
# ============================================================

# Default path; overridable per-process via MAESTRO_DISPATCH_LOG.
_DEFAULT_DISPATCH_LOG_PATH = (
    Path(__file__).resolve().parent.parent / "docs" / "data" / "dispatch-log.jsonl"
)

# Per-task per-tool sequence counter. Resets on process restart, but combined
# with a process-local random prefix the row_id stays globally unique within
# the JSONL file.
_DISPATCH_SEQ: dict[tuple[str, str], int] = {}
_DISPATCH_PREFIX = secrets.token_hex(4)
_DISPATCH_SCHEMA_VERSION = 1


def _next_seq(task_id: str, tool: str) -> int:
    key = (task_id or "noattr", tool)
    _DISPATCH_SEQ[key] = _DISPATCH_SEQ.get(key, 0) + 1
    return _DISPATCH_SEQ[key]


def _resolve_dispatch_log_path() -> Optional[Path]:
    """Return the path to write to, or None if telemetry is disabled.

    Three modes per design 56 § 2.2:
    - env var unset → default path
    - env var empty string → disabled (returns None)
    - env var non-empty → that path
    """
    raw = os.environ.get("MAESTRO_DISPATCH_LOG")
    if raw is None:
        return _DEFAULT_DISPATCH_LOG_PATH
    if raw == "":
        return None
    return Path(raw)


# ----------------------------------------------------------------
# T6.8: dispatch attribution chain (ADR-0011)
# ----------------------------------------------------------------

_BRANCH_RE = re.compile(r"^(?:feature|fix|refactor|docs)/(\d+)-")
_ENV_DEPRECATION_WARNED = False


def _warn_env_deprecation_once() -> None:
    """Emit DeprecationWarning the first time env-var attribution is used per process."""
    global _ENV_DEPRECATION_WARNED
    if _ENV_DEPRECATION_WARNED:
        return
    _ENV_DEPRECATION_WARNED = True
    warnings.warn(
        "MAESTRO_CURRENT_TASK / MAESTRO_CURRENT_ISSUE env vars for "
        "dispatch attribution are deprecated and will be removed in "
        "v0.0.4. Pass task_id / issue_number as parameters on each "
        "worker dispatch instead.",
        DeprecationWarning,
        stacklevel=2,
    )


def _infer_issue_from_branch() -> Optional[int]:
    """Read current git branch and parse its leading issue number.

    Returns None on any failure (no git, not a repo, regex miss, etc.).
    Recomputed per emit — branch can change mid-session.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if result.returncode != 0:
            return None
        m = _BRANCH_RE.match(result.stdout.strip())
        return int(m.group(1)) if m else None
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return None


def _resolve_attribution(
    task_id: Optional[str],
    issue_number: Optional[int],
) -> tuple[Optional[str], Optional[int]]:
    """Resolve dispatch attribution per ADR-0011 precedence chain.

    Order: explicit param > env var (deprecated) > git branch > unattributed.
    Partial-friendly: if either explicit param is provided, the other is
    NOT backfilled from env/branch. Avoids stale-env contamination of
    intentional partial attributions.
    """
    # Layer 1: explicit param (treat task_id="" as None;
    # issue_number=0 is allowed as a legitimate int)
    explicit_task = task_id if task_id else None
    if explicit_task is not None or issue_number is not None:
        return explicit_task, issue_number

    # Layer 2: env var (deprecated)
    env_task = os.environ.get("MAESTRO_CURRENT_TASK") or None
    env_issue_raw = os.environ.get("MAESTRO_CURRENT_ISSUE")
    env_issue: Optional[int] = None
    if env_issue_raw:
        try:
            env_issue = int(env_issue_raw)
        except ValueError:
            env_issue = None

    if env_task is not None or env_issue is not None:
        _warn_env_deprecation_once()
        return env_task, env_issue

    # Layer 3: git branch inference (only issue_number; task_id stays None)
    branch_issue = _infer_issue_from_branch()
    if branch_issue is not None:
        return None, branch_issue

    # Layer 4: unattributed
    return None, None


def _emit_dispatch_row(
    *,
    task_id: Optional[str] = None,
    issue_number: Optional[int] = None,
    tool: str,
    model: str,
    model_provider: str,
    started_at: float,
    duration: float,
    usage: Optional[dict],
    error: Optional[str],
) -> None:
    """Append one structured JSONL row for a dispatch.

    Schema per design 56 § 2.1. Attribution per ADR-0011 (T6.8). Fail-soft:
    any IOError logs to stderr and returns without raising — telemetry
    must never break a worker dispatch.
    """
    path = _resolve_dispatch_log_path()
    if path is None:
        return

    task_id, issue_number = _resolve_attribution(task_id, issue_number)

    seq = _next_seq(task_id or "noattr", tool)
    row_id = f"{_DISPATCH_PREFIX}-{task_id or 'noattr'}-{tool}-{seq}"

    started_iso = datetime.fromtimestamp(started_at, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    row = {
        "row_id": row_id,
        "task_id": task_id,
        "issue_number": issue_number,
        "tool": tool,
        "model": model,
        "model_provider": model_provider,
        "wall_s": duration,
        "prompt_tokens": (usage or {}).get("prompt_tokens"),
        "completion_tokens": (usage or {}).get("completion_tokens"),
        "total_tokens": (usage or {}).get("total_tokens"),
        "started_at": started_iso,
        "journal_ref": None,
        "is_estimate": False,
        "est_method": None,
        "supersedes": None,
        "schema_version": _DISPATCH_SCHEMA_VERSION,
        "error": error,
    }

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    except Exception as e:
        print(f"[maestro] dispatch row write failed: {e}", file=sys.stderr)


# ============================================================
# Shared helpers used by multiple roles
# ============================================================


def _build_banner(tool: str, model: str, duration: float, total_tokens: int) -> str:
    """Single source of truth for the dispatch banner shape.

    Coder prefixes this string onto its plaintext result_text. The three
    JSON workers (librarian / reviewer / scribe) embed the same string
    as the value of a `_banner` field inside their JSON output — placing
    a string before JSON would break json.loads() for every consumer.
    Shape parity is preserved; placement varies by output type.
    """
    return f"[{tool} dispatch — {model} — {duration}s — {total_tokens} tokens]"


def extract_banner(result_text: str) -> Optional[str]:
    """Retrieve the dispatch banner from result_text regardless of placement.

    Plaintext outputs (coder) carry the banner as a prefix; JSON outputs
    carry it inside a `_banner` field. Returns None if no banner is
    present (e.g. error-path responses, which intentionally have none —
    a banner with total_tokens=None would lie).
    """
    if result_text.startswith("["):
        return result_text.split("\n", 1)[0]
    try:
        obj = json.loads(result_text)
    except (json.JSONDecodeError, ValueError):
        return None
    if isinstance(obj, dict):
        banner = obj.get("_banner")
        if isinstance(banner, str):
            return banner
    return None


def _error_response(code: str, message: str, **extra: Any) -> list[TextContent]:
    """Build a JSON error response shared across roles.

    Roles return a stable `{error, message, ...}` envelope so the
    orchestrator can dispatch on the `error` key without parsing prose.
    """
    payload = {"error": code, "message": message}
    payload.update(extra)
    return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))]


# ============================================================
# Async dispatch infrastructure (ADR-0009)
#
# Every worker tool returns a job_id immediately and runs the actual
# work in a background asyncio task. The orchestrator polls
# `job_status(job_id)` until terminal. Sidesteps Claude Code's hard-
# coded ~60s MCP request timeout, which otherwise caps every worker
# dispatch.
# ============================================================


@dataclass
class JobRecord:
    """One in-flight (or completed) worker job's state.

    Held in a process-local dict; not persisted across server restarts
    (v0.0.3 scope per ADR-0009). `result_text` mirrors what the
    underlying handler would have returned synchronously — a JSON
    envelope from librarian/reviewer/scribe, formatted text from coder.
    """
    job_id: str
    tool: str
    status: str  # "running" | "done" | "failed"
    result_text: Optional[str] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None


_jobs: dict[str, JobRecord] = {}


async def _run_in_background(
    record: JobRecord, coro: Awaitable[list[TextContent]]
) -> None:
    """Run an impl coroutine and capture its result/exception in the record.

    Impl-level errors are already shaped as `_error_response` envelopes by
    the impl itself — those still land here as `done` with the envelope as
    `result_text`. `failed` is reserved for unhandled exceptions in the
    impl (i.e., bugs the role's own try/except didn't catch).
    """
    try:
        result_list = await coro
        record.result_text = result_list[0].text if result_list else ""
        record.status = "done"
    except Exception as e:
        record.error = f"{type(e).__name__}: {e}"
        record.status = "failed"
    finally:
        record.completed_at = time.time()


def _enqueue_dispatch(
    tool_name: str, coro: Awaitable[list[TextContent]]
) -> list[TextContent]:
    """Register a job, schedule the impl as a background task, return job_id."""
    job_id = str(uuid.uuid4())
    record = JobRecord(job_id=job_id, tool=tool_name, status="running")
    _jobs[job_id] = record
    asyncio.create_task(_run_in_background(record, coro))
    return [TextContent(
        type="text",
        text=json.dumps({"job_id": job_id}, ensure_ascii=False),
    )]


JOB_STATUS_TOOL = Tool(
    name="job_status",
    description=(
        "INFRASTRUCTURE TOOL — not a worker role. Poll the status of a "
        "previously-dispatched worker job. Given a job_id (returned by "
        "coder/librarian/reviewer/scribe), returns one of: "
        "{\"status\": \"running\"} (worker still in flight); "
        "{\"status\": \"done\", \"result_text\": ...} (work complete; "
        "result_text is what the underlying tool would have returned "
        "synchronously); or {\"status\": \"failed\", \"error\": ...} "
        "(unhandled exception in worker impl). Caller polls this every "
        "few seconds until terminal. DO NOT dispatch substantive work "
        "to this tool — it is a status probe, not a worker."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "job_id": {
                "type": "string",
                "description": (
                    "The job_id returned by an earlier worker dispatch. "
                    "Format: UUID4 string."
                ),
            },
        },
        "required": ["job_id"],
    },
)


async def job_status_handler(arguments: dict) -> list[TextContent]:
    """Look up a job record and report its status to the orchestrator."""
    job_id = arguments.get("job_id", "").strip()
    if not job_id:
        return _error_response("input_validation", "job_id is required")

    record = _jobs.get(job_id)
    if record is None:
        return _error_response("job_not_found", f"no job with id {job_id}")

    payload: dict[str, Any] = {"status": record.status, "tool": record.tool}
    if record.status == "done":
        payload["result_text"] = record.result_text
    elif record.status == "failed":
        payload["error"] = record.error
    return [TextContent(
        type="text",
        text=json.dumps(payload, ensure_ascii=False),
    )]


# ============================================================
# T1.6 — per-dispatch model resolution from team.yaml
#
# Each worker handler resolves its model at call time via team.yaml:
#   absent  → DEFAULT_MODELS fallback (zero-regression v0.0.2 path)
#   valid   → roles.<self>.model
#   invalid → refuse the dispatch with a structured error
#
# Events are appended best-effort to logs/team_events.jsonl as a stub;
# T3.1 ships proper Pydantic event models that supersede this format.
# ============================================================

from maestro.team.resolve import ResolveOk, ResolveRefuse, resolve_role_model
from maestro.dispatcher import run as dispatcher_run


def _emit_team_event(event: dict) -> None:
    """Append a team-resolution event to the dispatch log directory.

    Best-effort: any I/O failure is swallowed (per T1.6 brief — emission
    must never fail the dispatch). T3.1 will replace this stub.
    """
    try:
        log_path = LOG_DIR / "team_events.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps({**event, "ts": datetime.now().isoformat()}, ensure_ascii=False)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _resolve_role_or_refuse(role_id: str) -> Union[str, list[TextContent]]:
    """Resolve which model to dispatch for `role_id`, or return a refuse-response.

    Returns the model string when dispatch should proceed (emitting any
    fallback event as a side effect). Returns a list[TextContent] when
    team.yaml is invalid and the dispatch must abort early.
    """
    resolution = resolve_role_model(role_id, _PROJECT_ROOT)
    if isinstance(resolution, ResolveRefuse):
        _emit_team_event(resolution.event)
        return [TextContent(type="text", text=resolution.error_message)]
    if resolution.event is not None:
        _emit_team_event(resolution.event)
    return resolution.model


# ============================================================
# Role: coder (formerly cheap_code_gen)
#
# Generate code from a structured spec. The worker returns reasoning +
# code + concerns; the orchestrator reviews the concerns section before
# integrating. Single-shot, no multi-turn.
# ============================================================

CODER_TOOL = Tool(
    name="coder",
    description=(
        "Generate code via DeepSeek (cheap, fast worker). USE THIS for "
        "execution-heavy tasks where the spec is clear: CRUD endpoints, "
        "data classes, config files, scaffolds, standard React components, "
        "simple algorithm implementations, boilerplate of any kind. DO NOT "
        "USE for: architecture decisions, debugging that requires cross-file "
        "context, security-critical logic, or anything where you need deep "
        "reasoning about the existing codebase. The worker returns reasoning "
        "+ code + concerns; review the concerns section before integrating."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "spec": {
                "type": "string",
                "description": (
                    "Detailed specification. Include: language, framework, "
                    "function signatures or interfaces, expected behavior, "
                    "constraints, and any context the worker needs. "
                    "Be precise — vague specs produce vague code."
                ),
            },
            "language": {
                "type": "string",
                "description": "Programming language (python, typescript, go, rust, etc.)",
            },
            "task_id": {
                "type": "string",
                "description": (
                    "Optional task identifier (e.g., 'T6.8') for dispatch "
                    "telemetry attribution. See ADR-0011."
                ),
            },
            "issue_number": {
                "type": "integer",
                "description": (
                    "Optional issue number (e.g., 64) for dispatch telemetry "
                    "attribution. See ADR-0011."
                ),
            },
        },
        "required": ["spec", "language"],
    },
)


async def coder_handler(arguments: dict) -> list[TextContent]:
    """Enqueue the coder impl as a background job; return job_id immediately.

    See ADR-0009. Caller polls `job_status(job_id)` until terminal.
    """
    return _enqueue_dispatch("coder", _coder_impl(arguments))


async def _coder_impl(arguments: dict) -> list[TextContent]:
    """Dispatch a code-generation spec to DeepSeek via dispatcher.run.
    Lifecycle events (start/end/failed/fallback/refused) flow through
    the central dispatcher; the handler keeps prompt construction, cost
    telemetry (_emit_dispatch_row), and the banner-formatted output shape."""
    spec = arguments.get("spec", "").strip()
    language = arguments.get("language", "").strip()

    if not spec or not language:
        return [TextContent(
            type="text",
            text="ERROR: Both 'spec' and 'language' are required and must be non-empty."
        )]

    # T6.8 attribution fields (optional; ADR-0011)
    attribution_task_id = arguments.get("task_id")
    if attribution_task_id is not None and not isinstance(attribution_task_id, str):
        return [TextContent(type="text", text="ERROR: task_id must be a string when provided.")]
    attribution_issue_number = arguments.get("issue_number")
    if attribution_issue_number is not None and not isinstance(attribution_issue_number, int):
        return [TextContent(type="text", text="ERROR: issue_number must be an integer when provided.")]

    system_prompt = (
        f"You are a precise code generator working as part of an AI software team. "
        f"Generate {language} code that exactly meets the specification. "
        f"Follow standard conventions for {language}. "
        f"Do not add features the spec did not request."
        f"\n\n{STRUCTURED_RESPONSE_INSTRUCTION}"
    )

    user_prompt = f"Language: {language}\n\nSpecification:\n{spec}"

    # Captured in executor closure so the handler can build banner +
    # cost-telemetry row after dispatcher.run completes.
    captured_model: list[Optional[str]] = [None]
    captured_usage: dict = {}

    async def executor(model: str) -> str:
        captured_model[0] = model
        resp = await deepseek.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        captured_usage.update({
            "prompt_tokens": resp.usage.prompt_tokens,
            "completion_tokens": resp.usage.completion_tokens,
            "total_tokens": resp.usage.total_tokens,
        })
        return resp.choices[0].message.content

    start = time.time()
    try:
        result = await dispatcher_run("coder", user_prompt, executor)
    except asyncio.TimeoutError:
        duration = round(time.time() - start, 2)
        error_msg = f"Request to DeepSeek timed out after {REQUEST_TIMEOUT_SEC}s"
        _emit_dispatch_row(
            task_id=attribution_task_id,
            issue_number=attribution_issue_number,
            tool="coder",
            model=captured_model[0] or "unknown",
            model_provider="deepseek",
            started_at=start,
            duration=duration,
            usage=captured_usage or None,
            error=error_msg,
        )
        return [TextContent(
            type="text",
            text=(
                f"ERROR dispatching to coder ({captured_model[0]}): {error_msg}\n\n"
                f"Suggestion: handle this task yourself or retry."),
        )]
    except Exception as e:
        duration = round(time.time() - start, 2)
        error_msg = f"DeepSeek API error: {type(e).__name__}: {e}"
        _emit_dispatch_row(
            task_id=attribution_task_id,
            issue_number=attribution_issue_number,
            tool="coder",
            model=captured_model[0] or "unknown",
            model_provider="deepseek",
            started_at=start,
            duration=duration,
            usage=captured_usage or None,
            error=error_msg,
        )
        return [TextContent(
            type="text",
            text=(
                f"ERROR dispatching to coder ({captured_model[0]}): {error_msg}\n\n"
                f"Suggestion: handle this task yourself or retry."),
        )]

    duration = round(time.time() - start, 2)

    # dispatcher.run returns the error_message string on TeamConfigInvalid.
    # No deepseek call happened; no telemetry row (no real dispatch).
    if isinstance(result, str) and result.startswith("team.yaml at"):
        return [TextContent(type="text", text=result)]

    # Success path: dispatcher emitted start+end; emit cost telemetry + banner.
    _emit_dispatch_row(
        task_id=attribution_task_id,
        issue_number=attribution_issue_number,
        tool="coder",
        model=captured_model[0],
        model_provider="deepseek",
        started_at=start,
        duration=duration,
        usage=captured_usage,
        error=None,
    )
    banner = _build_banner("coder", captured_model[0], duration, captured_usage["total_tokens"])
    return [TextContent(
        type="text",
        text=f"{banner}\n\n{result}",
    )]


# ============================================================
# Role: librarian
#
# Read a long document and extract task-relevant content as structured
# JSON. The worker reads the file directly via file_path so the document
# text never enters the orchestrator's context — that's the load-bearing
# token-economy reason this role exists (see ADR-0008 § Worker file
# access).
# ============================================================

LIBRARIAN_SYSTEM_PROMPT = """You are a librarian on an AI software team. Your job is to read a long
reference document and extract exactly what the caller needs for the task
they describe. You return STRICT JSON matching the contract below.

The `hard_constraints[*].quote` field has a VERBATIM contract on words.
The handler that wraps you VERIFIES every quote against the source
document before returning to the caller. Quotes that don't match are
silently dropped from your output and reported as concerns.

The verifier is forgiving on rendering, strict on words:

- Whitespace: free to normalize. Line wraps and indentation in source
  collapse to single spaces in the comparison.
- Markdown bold (`**X**`): the verifier strips `**` from both sides
  before comparing. You don't need to preserve bold markers — write
  `X` or `**X**`, both pass.
- All other characters: must match exactly. Backticks (`` `pm` ``
  ≠ `pm`), brackets, parentheses, em-dashes, every punctuation mark.
- Word identity: same words in the same order. Adding a period,
  dropping a leading word like "plus a", or substituting a synonym
  is a contract violation.

Examples:
- Source: `**X** enforces Y`, your quote: `X enforces Y`
  → OK (markdown bold stripped by verifier).
- Source: `plus a Z constant sourced from W`, your quote: `Z constant sourced from W.`
  → VIOLATION (dropped "plus a", appended period — word change).
- Source: `text\\n  more text`, your quote: `text more text`
  → OK (whitespace normalized).
- Source contains the backticked identifier `pm`, your quote: `pm` (no backticks)
  → VIOLATION (backticks carry "literal identifier" meaning).

If you cannot find a verbatim constraint for a point you want to make,
OMIT the entry rather than invent or rephrase. The summary field is
where paraphrase belongs.

Other rules:
- In `summary`, paraphrase freely; this is your understanding.
- In `recommend_full_read`, list section names where you are not
  confident your summary captures the nuance. Better to be honest
  than confident.
- In `concerns`, surface anything that surprised you, contradicted
  other docs in your context, or seemed under-specified.

Return JSON of exactly this shape:
{
  "hard_constraints": [{"quote": "...", "section": "..."}],
  "summary": "...",
  "recommend_full_read": ["..."],
  "concerns": ["..."]
}
Empty lists are allowed. Do NOT include any text outside the JSON object."""

# Soft cap on documents the librarian will accept inline. ~20K tokens for
# v4-flash. Above this, the handler refuses rather than truncating, so
# the caller decides whether to slice or split.
MAX_DOCUMENT_CHARS = 80000


LIBRARIAN_TOOL = Tool(
    name="librarian",
    description=(
        "Extract task-relevant content from long documents (design docs, ADRs, "
        "journal entries). USE for: focused reading of large reference material to "
        "surface constraints, decisions, and relevant context. The worker reads the "
        "file directly when given file_path, keeping the document out of the caller's "
        "context. DO NOT USE for: reading code (use a code-review tool instead); "
        "documents you have already cited specific lines from; live operational data."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": (
                    "Absolute or repo-relative path to the document. Worker reads "
                    "the file. PREFERRED when the document is on disk — keeps the "
                    "document text out of the caller's context."
                ),
            },
            "document_text": {
                "type": "string",
                "description": (
                    "Inline document content. Use only when source is not a file "
                    "(e.g., remote API response)."
                ),
            },
            "query": {
                "type": "string",
                "description": (
                    "What the caller is looking for. Be specific. "
                    "E.g., 'I am implementing T0.2 of Epic 0; surface relevant "
                    "constraints from this design doc.'"
                ),
            },
            "task_id": {
                "type": "string",
                "description": (
                    "Optional task identifier (e.g., 'T6.8') for dispatch "
                    "telemetry attribution. See ADR-0011."
                ),
            },
            "issue_number": {
                "type": "integer",
                "description": (
                    "Optional issue number (e.g., 64) for dispatch telemetry "
                    "attribution. See ADR-0011."
                ),
            },
        },
        "required": ["query"],
    },
)


def _normalize_for_verbatim(text: str) -> str:
    """Normalize text for semantic-verbatim comparison.

    The verbatim contract is about word content, not rendering. We
    therefore strip:
      - Whitespace runs (line wraps, indentation → single space).
      - Markdown bold markers (`**X**` becomes `X`). The orchestrator
        cares what the doc says, not how it's emphasized.

    What we deliberately do NOT strip:
      - Backticks. `pm` (literal identifier) is a different signal from
        `pm` (English word).
      - Underscores. `__init__` is a Python identifier, not bold markup.
      - Brackets, parens, em-dashes, all other punctuation. Word-level
        identity must hold.
    """
    return " ".join(text.replace("**", "").split())


def _verify_verbatim_quotes(
    quotes: list, source: str
) -> tuple[list, list[str]]:
    """Drop hard_constraints entries whose quote does not match the source.

    Comparison uses semantic-verbatim normalization (whitespace +
    markdown bold). Word-level changes — added, dropped, or substituted
    words; punctuation that affects meaning — are still rejected. See
    ADR-0008 § Verbatim verification for the convention; this function
    is the contract enforcer.

    Returns (kept, violation_notes). Violation notes describe each
    dropped entry so the caller can see what didn't pass.
    """
    normalized_source = _normalize_for_verbatim(source)
    kept = []
    violations = []
    for i, hc in enumerate(quotes):
        quote = hc.get("quote", "")
        normalized_quote = _normalize_for_verbatim(quote)
        if normalized_quote and normalized_quote in normalized_source:
            kept.append(hc)
        else:
            violations.append(
                f"hard_constraints[{i}] not verbatim "
                f"(section={hc.get('section', '?')!r}); dropped"
            )
    return kept, violations


def _validate_librarian_output(data: Any) -> Optional[str]:
    """Verify the parsed JSON output matches the librarian contract.

    Returns None on success, or a short string explaining the violation.
    Extra fields are ignored (forward compatibility).
    """
    if not isinstance(data, dict):
        return "output is not a dict"

    required_keys = ("hard_constraints", "summary", "recommend_full_read", "concerns")
    for key in required_keys:
        if key not in data:
            return f"missing key: {key}"

    hc = data["hard_constraints"]
    if not isinstance(hc, list):
        return "hard_constraints is not a list"
    for i, item in enumerate(hc):
        if not isinstance(item, dict):
            return f"hard_constraints[{i}] is not a dict"
        for field in ("quote", "section"):
            if field not in item:
                return f"hard_constraints[{i}].{field} is missing"
            if not isinstance(item[field], str) or not item[field]:
                return f"hard_constraints[{i}].{field} is not a non-empty string"

    if not isinstance(data["summary"], str):
        return "summary is not a string"

    rfr = data["recommend_full_read"]
    if not isinstance(rfr, list):
        return "recommend_full_read is not a list"
    for i, item in enumerate(rfr):
        if not isinstance(item, str):
            return f"recommend_full_read[{i}] is not a string"

    concerns = data["concerns"]
    if not isinstance(concerns, list):
        return "concerns is not a list"
    for i, item in enumerate(concerns):
        if not isinstance(item, str):
            return f"concerns[{i}] is not a string"

    return None


async def librarian_handler(arguments: dict) -> list[TextContent]:
    """Enqueue the librarian impl as a background job; return job_id immediately.

    See ADR-0009. Caller polls `job_status(job_id)` until terminal.
    """
    return _enqueue_dispatch("librarian", _librarian_impl(arguments))


async def _librarian_impl(arguments: dict) -> list[TextContent]:
    """Read a document (from file_path or inline) and extract content matching the query."""
    file_path = arguments.get("file_path")
    document_text = arguments.get("document_text")
    query = arguments.get("query", "").strip()

    # XOR contract: exactly one of file_path or document_text must be present.
    has_path = bool(file_path)
    has_text = bool(document_text)
    if has_path == has_text:
        return _error_response(
            "input_validation",
            "exactly one of file_path or document_text required",
        )

    if not query:
        return _error_response("input_validation", "query is required")

    # T6.8 attribution fields (optional; ADR-0011)
    attribution_task_id = arguments.get("task_id")
    if attribution_task_id is not None and not isinstance(attribution_task_id, str):
        return _error_response("input_validation", "task_id must be a string")
    attribution_issue_number = arguments.get("issue_number")
    if attribution_issue_number is not None and not isinstance(attribution_issue_number, int):
        return _error_response("input_validation", "issue_number must be an integer")

    # T1.6 — resolve role's model from team.yaml, or refuse if invalid.
    model_or_refuse = _resolve_role_or_refuse("librarian")
    if isinstance(model_or_refuse, list):
        return model_or_refuse
    model = model_or_refuse

    # The whole point of the role is to keep document_text out of the
    # caller's context — only the worker sees the bytes.
    if file_path:
        # Resolve relative paths against the project root rather than the
        # MCP server's CWD (which is the launching client's working
        # directory, often unrelated to the repo). Lets callers pass
        # repo-relative paths like "docs/design/13-...".
        resolved_path = Path(file_path)
        if not resolved_path.is_absolute():
            resolved_path = _PROJECT_ROOT / resolved_path
        try:
            with open(resolved_path, encoding="utf-8") as f:
                document_text = f.read()
        except FileNotFoundError:
            return _error_response(
                "file_not_found",
                f"file_path not found: {file_path} (resolved: {resolved_path})",
            )
        except Exception as e:
            return _error_response("file_read_error", f"{type(e).__name__}: {e}")

    if len(document_text) > MAX_DOCUMENT_CHARS:
        return _error_response(
            "document_too_large",
            f"document is {len(document_text)} chars (limit {MAX_DOCUMENT_CHARS}); "
            "pass a smaller slice via document_text or split the request",
        )

    start = time.time()
    error_msg = None
    raw = None
    parsed = None
    usage = None

    try:
        resp = await deepseek.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": LIBRARIAN_SYSTEM_PROMPT},
                {"role": "user", "content": f"Query: {query}\n\nDocument:\n{document_text}"},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        raw = resp.choices[0].message.content
        usage = {
            "prompt_tokens": resp.usage.prompt_tokens,
            "completion_tokens": resp.usage.completion_tokens,
            "total_tokens": resp.usage.total_tokens,
        }
    except asyncio.TimeoutError:
        error_msg = "model_timeout"
    except Exception as e:
        error_msg = f"model_api_error: {type(e).__name__}: {e}"

    duration = round(time.time() - start, 2)

    # Log dispatch metadata (NOT the document text — it'd defeat the point).
    log_dispatch({
        "ts": datetime.now().isoformat(),
        "tool": "librarian",
        "model": model,
        "input": {
            "file_path": file_path,
            "has_inline_document": bool(arguments.get("document_text")),
            "document_chars": len(document_text),
            "query": query,
        },
        "output_raw_chars": len(raw) if raw else None,
        "error": error_msg,
        "duration_sec": duration,
        "usage": usage,
    })
    _emit_dispatch_row(
        task_id=attribution_task_id,
        issue_number=attribution_issue_number,
        tool="librarian",
        model=model,
        model_provider="deepseek",
        started_at=start,
        duration=duration,
        usage=usage,
        error=error_msg,
    )

    if error_msg:
        return _error_response("model_api_error", error_msg)

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        return _error_response("output_not_json", str(e), raw=raw[:500])

    validation_error = _validate_librarian_output(parsed)
    if validation_error:
        return _error_response("output_schema_invalid", validation_error, raw=parsed)

    # Verbatim contract enforcement: the system prompt asks for verbatim
    # quotes but workers regularly drop markdown emphasis or paraphrase.
    # The verifier is the actual contract — non-verbatim quotes never
    # reach the orchestrator.
    kept_quotes, violations = _verify_verbatim_quotes(
        parsed["hard_constraints"], document_text
    )
    parsed["hard_constraints"] = kept_quotes
    if violations:
        summary_note = (
            f"librarian self-validation dropped {len(violations)} "
            f"non-verbatim quote(s) from hard_constraints "
            f"(kept {len(kept_quotes)})"
        )
        parsed["concerns"] = (
            [summary_note] + list(parsed.get("concerns", [])) + violations
        )

    parsed["_banner"] = _build_banner(
        "librarian", model, duration, usage["total_tokens"]
    )
    return [TextContent(
        type="text",
        text=json.dumps(parsed, ensure_ascii=False, indent=2),
    )]


# ============================================================
# Role: reviewer
#
# Judge whether code matches a spec. Returns a verdict (pass/concerns/
# fail) plus structured findings. NOT a refactorer or architect — the
# system prompt forbids style and design opinions; only correspondence
# to the spec is in scope.
# ============================================================

REVIEWER_SYSTEM_PROMPT = """You are a code reviewer on an AI software team. Your job is to judge whether
code matches a spec. You are NOT here to redesign, refactor, or improve style
— only to verify correspondence to the spec.

You return STRICT JSON matching the contract below.

Strict rules:
- Verdict `pass` requires every spec requirement to be addressed.
- Verdict `fail` requires at least one high-severity finding OR at least one
  missed requirement.
- Verdict `concerns` means the code addresses the spec but has medium/low
  issues worth surfacing.
- Cite specific function names or line ranges in `location`. "the code" is
  not a location.
- If the spec is ambiguous, flag in `concerns` rather than guessing.
- Do NOT comment on style choices the spec didn't address.

Return JSON of exactly this shape:
{
  "verdict": "pass" | "concerns" | "fail",
  "findings": [
    {"severity": "high" | "medium" | "low",
     "location": "...",
     "description": "..."}
  ],
  "missed_requirements": ["..."],
  "concerns": ["..."]
}
Empty lists are allowed. Do NOT include any text outside the JSON object."""


REVIEWER_TOOL = Tool(
    name="reviewer",
    description=(
        "Review code against a spec. USE for: pass/fail judgment on whether "
        "worker-generated code matches a spec; finding spec/code drift; "
        "flagging missed acceptance criteria. DO NOT USE for: subjective style "
        "review; architectural decisions; security review; cross-file reasoning."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "spec": {
                "type": "string",
                "description": (
                    "The spec the code was supposed to implement, including "
                    "hard constraints and acceptance criteria."
                ),
            },
            "code": {
                "type": "string",
                "description": "The code under review.",
            },
            "language": {
                "type": "string",
                "description": "Programming language (python, typescript, etc.).",
            },
            "task_id": {
                "type": "string",
                "description": (
                    "Optional task identifier (e.g., 'T6.8') for dispatch "
                    "telemetry attribution. See ADR-0011."
                ),
            },
            "issue_number": {
                "type": "integer",
                "description": (
                    "Optional issue number (e.g., 64) for dispatch telemetry "
                    "attribution. See ADR-0011."
                ),
            },
        },
        "required": ["spec", "code", "language"],
    },
)


_REVIEWER_VERDICTS = ("pass", "concerns", "fail")
_REVIEWER_SEVERITIES = ("high", "medium", "low")


def _validate_reviewer_output(data: Any) -> Optional[str]:
    """Verify the parsed JSON output matches the reviewer contract.

    Returns None on success, or a short string explaining the violation.
    Extra fields are ignored (forward compatibility).
    """
    if not isinstance(data, dict):
        return "output is not a dict"

    for key in ("verdict", "findings", "missed_requirements", "concerns"):
        if key not in data:
            return f"missing key: {key}"

    if data["verdict"] not in _REVIEWER_VERDICTS:
        return (
            f"verdict {data['verdict']!r} not in allowed values "
            f"{_REVIEWER_VERDICTS}"
        )

    findings = data["findings"]
    if not isinstance(findings, list):
        return "findings is not a list"
    for i, item in enumerate(findings):
        if not isinstance(item, dict):
            return f"findings[{i}] is not a dict"
        for field in ("severity", "location", "description"):
            if field not in item:
                return f"findings[{i}].{field} is missing"
        if item["severity"] not in _REVIEWER_SEVERITIES:
            return (
                f"findings[{i}].severity {item['severity']!r} not in allowed "
                f"values {_REVIEWER_SEVERITIES}"
            )
        for field in ("location", "description"):
            if not isinstance(item[field], str) or not item[field]:
                return f"findings[{i}].{field} is not a non-empty string"

    missed = data["missed_requirements"]
    if not isinstance(missed, list):
        return "missed_requirements is not a list"
    for i, item in enumerate(missed):
        if not isinstance(item, str):
            return f"missed_requirements[{i}] is not a string"

    concerns = data["concerns"]
    if not isinstance(concerns, list):
        return "concerns is not a list"
    for i, item in enumerate(concerns):
        if not isinstance(item, str):
            return f"concerns[{i}] is not a string"

    return None


async def reviewer_handler(arguments: dict) -> list[TextContent]:
    """Enqueue the reviewer impl as a background job; return job_id immediately.

    See ADR-0009. Caller polls `job_status(job_id)` until terminal.
    """
    return _enqueue_dispatch("reviewer", _reviewer_impl(arguments))


async def _reviewer_impl(arguments: dict) -> list[TextContent]:
    """Judge whether code matches a spec; return structured verdict + findings."""
    spec = arguments.get("spec", "").strip()
    code = arguments.get("code", "").strip()
    language = arguments.get("language", "").strip()

    if not spec or not code or not language:
        return _error_response(
            "input_validation",
            "spec, code, and language are all required and must be non-empty",
        )

    # T6.8 attribution fields (optional; ADR-0011)
    attribution_task_id = arguments.get("task_id")
    if attribution_task_id is not None and not isinstance(attribution_task_id, str):
        return _error_response("input_validation", "task_id must be a string")
    attribution_issue_number = arguments.get("issue_number")
    if attribution_issue_number is not None and not isinstance(attribution_issue_number, int):
        return _error_response("input_validation", "issue_number must be an integer")

    # T1.6 — resolve role's model from team.yaml, or refuse if invalid.
    model_or_refuse = _resolve_role_or_refuse("reviewer")
    if isinstance(model_or_refuse, list):
        return model_or_refuse
    model = model_or_refuse

    user_prompt = f"Language: {language}\n\nSpec:\n{spec}\n\nCode:\n{code}"

    start = time.time()
    error_msg = None
    raw = None
    parsed = None
    usage = None

    try:
        resp = await deepseek.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": REVIEWER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        raw = resp.choices[0].message.content
        usage = {
            "prompt_tokens": resp.usage.prompt_tokens,
            "completion_tokens": resp.usage.completion_tokens,
            "total_tokens": resp.usage.total_tokens,
        }
    except asyncio.TimeoutError:
        error_msg = "model_timeout"
    except Exception as e:
        error_msg = f"model_api_error: {type(e).__name__}: {e}"

    duration = round(time.time() - start, 2)

    # Log only metadata, not the spec/code text — both are already in the
    # caller's context for the same task being reviewed.
    log_dispatch({
        "ts": datetime.now().isoformat(),
        "tool": "reviewer",
        "model": model,
        "input": {
            "spec_chars": len(spec),
            "code_chars": len(code),
            "language": language,
        },
        "output_raw_chars": len(raw) if raw else None,
        "error": error_msg,
        "duration_sec": duration,
        "usage": usage,
    })
    _emit_dispatch_row(
        task_id=attribution_task_id,
        issue_number=attribution_issue_number,
        tool="reviewer",
        model=model,
        model_provider="deepseek",
        started_at=start,
        duration=duration,
        usage=usage,
        error=error_msg,
    )

    if error_msg:
        return _error_response("model_api_error", error_msg)

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        return _error_response("output_not_json", str(e), raw=raw[:500])

    validation_error = _validate_reviewer_output(parsed)
    if validation_error:
        return _error_response("output_schema_invalid", validation_error, raw=parsed)

    parsed["_banner"] = _build_banner(
        "reviewer", model, duration, usage["total_tokens"]
    )
    return [TextContent(
        type="text",
        text=json.dumps(parsed, ensure_ascii=False, indent=2),
    )]


# ============================================================
# Role: scribe
#
# Draft commit messages and PR bodies from a diff plus issue context.
# Routine text generation — flash-tier model is sufficient.
# ============================================================

SCRIBE_SYSTEM_PROMPT = """You are a scribe on an AI software team. Your job is to write commit messages
and PR bodies that follow the project's conventions exactly.

You return STRICT JSON matching the contract below.

Strict rules:
- Subject line under 80 chars; use Conventional Commits prefix
  (feat / fix / docs / refactor / test / chore / etc).
- Body explains the WHY (motivation, decision), not the WHAT (the diff itself
  shows the WHAT).
- Include `Closes #N.` on its own line if the convention says so. Otherwise use
  `Refs #N.` per the convention text.
- Include co-author lines per the convention.
- Do NOT invent details not present in the diff or issue.
- If the diff is large or ambiguous, flag in `concerns` rather than overstating
  what changed.

Return JSON of exactly this shape:
{
  "commit_message": "...",
  "pr_title": "...",
  "pr_body": "...",
  "concerns": ["..."]
}
- `commit_message`: full subject + body, including any co-author lines.
- `pr_title`: under 70 chars per Maestro convention.
- `pr_body`: Markdown, following the project's PR body convention from the
  `convention` field of the input.
Empty `concerns` list is allowed. Do NOT include any text outside the JSON object."""


SCRIBE_TOOL = Tool(
    name="scribe",
    description=(
        "Draft commit messages and PR bodies. USE for: Conventional Commits "
        "message + PR body from a git diff plus issue context. DO NOT USE for: "
        "release notes (different scope); code comments; user-facing documentation."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "diff": {
                "type": "string",
                "description": "Output of `git diff` for the change being committed.",
            },
            "issue_number": {
                "type": "integer",
                "description": "Issue number this commit addresses.",
            },
            "issue_title": {
                "type": "string",
                "description": "Title of the issue being addressed.",
            },
            "issue_body": {
                "type": "string",
                "description": "Body of the issue (for context on scope and acceptance criteria).",
            },
            "convention": {
                "type": "string",
                "description": (
                    "Project's commit message and PR body conventions. Include "
                    "Conventional Commits prefix rules, co-author attribution "
                    "format, and Closes/Refs placement rules."
                ),
            },
            "task_id": {
                "type": "string",
                "description": (
                    "Optional task identifier (e.g., 'T6.8') for dispatch "
                    "telemetry attribution. See ADR-0011. (issue_number "
                    "above doubles as attribution issue.)"
                ),
            },
        },
        "required": ["diff", "issue_number", "issue_title", "issue_body", "convention"],
    },
)


def _validate_scribe_output(data: Any) -> Optional[str]:
    """Verify the parsed JSON output matches the scribe contract.

    Returns None on success, or a short string explaining the violation.
    Extra fields are ignored (forward compatibility).
    """
    if not isinstance(data, dict):
        return "output is not a dict"

    for key in ("commit_message", "pr_title", "pr_body", "concerns"):
        if key not in data:
            return f"missing key: {key}"

    for key in ("commit_message", "pr_title"):
        if not isinstance(data[key], str) or not data[key]:
            return f"{key} is not a non-empty string"

    if not isinstance(data["pr_body"], str):
        return "pr_body is not a string"

    concerns = data["concerns"]
    if not isinstance(concerns, list):
        return "concerns is not a list"
    for i, item in enumerate(concerns):
        if not isinstance(item, str):
            return f"concerns[{i}] is not a string"

    return None


async def scribe_handler(arguments: dict) -> list[TextContent]:
    """Enqueue the scribe impl as a background job; return job_id immediately.

    See ADR-0009. Caller polls `job_status(job_id)` until terminal.
    """
    return _enqueue_dispatch("scribe", _scribe_impl(arguments))


async def _scribe_impl(arguments: dict) -> list[TextContent]:
    """Draft a commit message and PR body from a diff + issue context."""
    diff = arguments.get("diff", "").strip()
    issue_number = arguments.get("issue_number")
    issue_title = arguments.get("issue_title", "").strip()
    issue_body = arguments.get("issue_body", "").strip()
    convention = arguments.get("convention", "").strip()

    if not diff:
        return _error_response("input_validation", "diff is required and must be non-empty")
    if not isinstance(issue_number, int):
        return _error_response("input_validation", "issue_number must be an integer")
    if not issue_title:
        return _error_response("input_validation", "issue_title is required")
    if not convention:
        return _error_response("input_validation", "convention is required")
    # issue_body may be empty — some issues are very terse; we don't require it.

    # T6.8 attribution: scribe reuses the existing required `issue_number`
    # for attribution; only `task_id` is a new optional field (ADR-0011).
    attribution_task_id = arguments.get("task_id")
    if attribution_task_id is not None and not isinstance(attribution_task_id, str):
        return _error_response("input_validation", "task_id must be a string")
    attribution_issue_number = issue_number  # already validated above

    # T1.6 — resolve role's model from team.yaml, or refuse if invalid.
    model_or_refuse = _resolve_role_or_refuse("scribe")
    if isinstance(model_or_refuse, list):
        return model_or_refuse
    model = model_or_refuse

    user_prompt = (
        f"Issue #{issue_number}: {issue_title}\n\n"
        f"Issue body:\n{issue_body}\n\n"
        f"Project conventions:\n{convention}\n\n"
        f"Diff:\n{diff}"
    )

    start = time.time()
    error_msg = None
    raw = None
    parsed = None
    usage = None

    try:
        resp = await deepseek.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SCRIBE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        raw = resp.choices[0].message.content
        usage = {
            "prompt_tokens": resp.usage.prompt_tokens,
            "completion_tokens": resp.usage.completion_tokens,
            "total_tokens": resp.usage.total_tokens,
        }
    except asyncio.TimeoutError:
        error_msg = "model_timeout"
    except Exception as e:
        error_msg = f"model_api_error: {type(e).__name__}: {e}"

    duration = round(time.time() - start, 2)

    # Log metadata only — diff and issue body are already in the caller's
    # context for the commit being drafted.
    log_dispatch({
        "ts": datetime.now().isoformat(),
        "tool": "scribe",
        "model": model,
        "input": {
            "diff_chars": len(diff),
            "issue_number": issue_number,
            "issue_title": issue_title,
        },
        "output_raw_chars": len(raw) if raw else None,
        "error": error_msg,
        "duration_sec": duration,
        "usage": usage,
    })
    _emit_dispatch_row(
        task_id=attribution_task_id,
        issue_number=attribution_issue_number,
        tool="scribe",
        model=model,
        model_provider="deepseek",
        started_at=start,
        duration=duration,
        usage=usage,
        error=error_msg,
    )

    if error_msg:
        return _error_response("model_api_error", error_msg)

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        return _error_response("output_not_json", str(e), raw=raw[:500])

    validation_error = _validate_scribe_output(parsed)
    if validation_error:
        return _error_response("output_schema_invalid", validation_error, raw=parsed)

    parsed["_banner"] = _build_banner(
        "scribe", model, duration, usage["total_tokens"]
    )
    return [TextContent(
        type="text",
        text=json.dumps(parsed, ensure_ascii=False, indent=2),
    )]


# ============================================================
# Tool registry — single source of truth.
# Adding a new role = one (Tool, handler) entry below.
# ============================================================

ToolHandler = Callable[[dict], Awaitable[list[TextContent]]]

TOOLS_REGISTRY: dict[str, tuple[Tool, ToolHandler]] = {
    CODER_TOOL.name: (CODER_TOOL, coder_handler),
    LIBRARIAN_TOOL.name: (LIBRARIAN_TOOL, librarian_handler),
    REVIEWER_TOOL.name: (REVIEWER_TOOL, reviewer_handler),
    SCRIBE_TOOL.name: (SCRIBE_TOOL, scribe_handler),
    JOB_STATUS_TOOL.name: (JOB_STATUS_TOOL, job_status_handler),
}


# ============================================================
# MCP Server
# ============================================================

app = Server("maestro")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [tool for tool, _ in TOOLS_REGISTRY.values()]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    entry = TOOLS_REGISTRY.get(name)
    if entry is None:
        return [TextContent(type="text", text=f"ERROR: Unknown tool '{name}'")]
    _, handler = entry
    return await handler(arguments)


# ============================================================
# Entry point
# ============================================================

async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
