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

DEEPSEEK_MODEL = os.environ.get("MAESTRO_DEEPSEEK_MODEL", "deepseek-coder")
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
# MCP Server
# ============================================================

app = Server("maestro")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="cheap_code_gen",
            description=(
                "Generate code via DeepSeek-Coder (cheap, fast worker). "
                "USE THIS for execution-heavy tasks where the spec is clear: "
                "CRUD endpoints, data classes, config files, scaffolds, "
                "standard React components, simple algorithm implementations, "
                "boilerplate of any kind. "
                "DO NOT USE for: architecture decisions, debugging that requires "
                "cross-file context, security-critical logic, or anything where "
                "you need deep reasoning about the existing codebase. "
                "The worker returns reasoning + code + concerns; review the "
                "concerns section before integrating."
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
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name != "cheap_code_gen":
        return [TextContent(type="text", text=f"ERROR: Unknown tool '{name}'")]

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
            model=DEEPSEEK_MODEL,
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

    # Always log, even on failure
    log_dispatch({
        "ts": datetime.now().isoformat(),
        "tool": name,
        "model": DEEPSEEK_MODEL,
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
                f"ERROR dispatching to junior_engineer ({DEEPSEEK_MODEL}): {error_msg}\n\n"
                f"Suggestion: handle this task yourself or retry."
            )
        )]

    # Return the full structured response to the orchestrator.
    # The orchestrator (Opus) sees reasoning + output + concerns and can act on them.
    return [TextContent(
        type="text",
        text=(
            f"[junior_engineer dispatch — {DEEPSEEK_MODEL} — {duration}s — "
            f"{usage['total_tokens']} tokens]\n\n{response_text}"
        )
    )]


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
