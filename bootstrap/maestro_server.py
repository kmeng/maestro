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
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

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

# ============================================================
# Configuration
# ============================================================


def _load_dotenv(path: Path) -> None:
    """Read KEY=VALUE lines from path into os.environ.

    - Values in the file overwrite any existing os.environ entry, making
      .env the single authoritative source when present.
    - Lines starting with # or without '=' are ignored.
    - Surrounding single/double quotes on the value are stripped.
    - Silently no-op if path does not exist.
    """
    if not path.is_file():
        return
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip()
            if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
                val = val[1:-1]
            os.environ[key] = val


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_load_dotenv(_PROJECT_ROOT / ".env")

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    env_path = _PROJECT_ROOT / ".env"
    if not env_path.is_file():
        print(
            f"ERROR: DEEPSEEK_API_KEY not set.\n"
            f"  Copy {_PROJECT_ROOT}/.env.example to {env_path} and add your key.",
            file=sys.stderr,
        )
    else:
        print(
            f"ERROR: DEEPSEEK_API_KEY not set in {env_path}.\n"
            f"  Add a line: DEEPSEEK_API_KEY=your-key-here",
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
# Shared helpers used by multiple roles
# ============================================================

def _error_response(code: str, message: str, **extra: Any) -> list[TextContent]:
    """Build a JSON error response shared across roles.

    Roles return a stable `{error, message, ...}` envelope so the
    orchestrator can dispatch on the `error` key without parsing prose.
    """
    payload = {"error": code, "message": message}
    payload.update(extra)
    return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))]


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
        },
        "required": ["spec", "language"],
    },
)


async def coder_handler(arguments: dict) -> list[TextContent]:
    """Dispatch a code-generation spec to DeepSeek and return the raw structured response."""
    spec = arguments.get("spec", "").strip()
    language = arguments.get("language", "").strip()

    if not spec or not language:
        return [TextContent(
            type="text",
            text="ERROR: Both 'spec' and 'language' are required and must be non-empty."
        )]

    system_prompt = (
        f"You are a precise code generator working as part of an AI software team. "
        f"Generate {language} code that exactly meets the specification. "
        f"Follow standard conventions for {language}. "
        f"Do not add features the spec did not request."
        f"\n\n{STRUCTURED_RESPONSE_INSTRUCTION}"
    )

    user_prompt = f"Language: {language}\n\nSpecification:\n{spec}"

    start = time.time()
    error_msg = None
    response_text = None
    usage = None

    try:
        resp = await deepseek.chat.completions.create(
            model=MODEL_PRO,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        response_text = resp.choices[0].message.content
        usage = {
            "prompt_tokens": resp.usage.prompt_tokens,
            "completion_tokens": resp.usage.completion_tokens,
            "total_tokens": resp.usage.total_tokens,
        }
    except asyncio.TimeoutError:
        error_msg = f"Request to DeepSeek timed out after {REQUEST_TIMEOUT_SEC}s"
    except Exception as e:
        error_msg = f"DeepSeek API error: {type(e).__name__}: {e}"

    duration = round(time.time() - start, 2)

    # Always log, even on failure — observability matters more than success ratio.
    log_dispatch({
        "ts": datetime.now().isoformat(),
        "tool": "coder",
        "model": MODEL_PRO,
        "input": arguments,
        "output": response_text,
        "error": error_msg,
        "duration_sec": duration,
        "usage": usage,
    })

    if error_msg:
        return [TextContent(
            type="text",
            text=(
                f"ERROR dispatching to coder ({MODEL_PRO}): {error_msg}\n\n"
                f"Suggestion: handle this task yourself or retry."
            )
        )]

    return [TextContent(
        type="text",
        text=(
            f"[coder dispatch — {MODEL_PRO} — {duration}s — "
            f"{usage['total_tokens']} tokens]\n\n{response_text}"
        )
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
            model=MODEL_FLASH,
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
        "model": MODEL_FLASH,
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
