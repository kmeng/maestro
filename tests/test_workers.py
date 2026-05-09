"""
Tests for Maestro's worker roles in bootstrap/maestro_server.py.

Covers:
  - tool registration (TOOLS_REGISTRY contents)
  - librarian I/O contract: input validation, file read, size cap,
    model invocation, output schema validation, error envelope
  - coder I/O contract: input validation; full happy-path/API-error
    coverage is intentionally lighter — coder is largely unchanged
    from v0.0.2 and well-exercised in production
  - _validate_librarian_output contract surface

All DeepSeek API calls are mocked; tests run offline.
"""

import asyncio
import importlib.util
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest


# ============================================================
# Module loading — bootstrap/maestro_server.py is not a package,
# so we load it via importlib once and share across tests.
# ============================================================

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BOOTSTRAP = _REPO_ROOT / "bootstrap" / "maestro_server.py"


@pytest.fixture(scope="module")
def server():
    spec = importlib.util.spec_from_file_location("maestro_server", _BOOTSTRAP)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ============================================================
# Tool registry
# ============================================================


def test_tools_registry_contains_coder_and_librarian(server):
    assert set(server.TOOLS_REGISTRY.keys()) == {"coder", "librarian"}


def test_coder_tool_has_required_input_fields(server):
    schema = server.CODER_TOOL.inputSchema
    assert set(schema["required"]) == {"spec", "language"}


def test_librarian_tool_requires_query_only(server):
    """file_path and document_text are XOR — handler enforces exactly-one."""
    schema = server.LIBRARIAN_TOOL.inputSchema
    assert schema["required"] == ["query"]
    props = schema["properties"]
    assert "file_path" in props
    assert "document_text" in props
    assert "query" in props


# ============================================================
# _validate_librarian_output
# ============================================================


def test_validate_accepts_minimal_valid(server):
    valid = {
        "hard_constraints": [],
        "summary": "",
        "recommend_full_read": [],
        "concerns": [],
    }
    assert server._validate_librarian_output(valid) is None


def test_validate_accepts_full_valid(server):
    valid = {
        "hard_constraints": [
            {"quote": "must do X", "section": "§3.2"},
        ],
        "summary": "the doc says X",
        "recommend_full_read": ["§5"],
        "concerns": ["ambiguous wording in §4"],
    }
    assert server._validate_librarian_output(valid) is None


def test_validate_rejects_non_dict(server):
    assert "not a dict" in server._validate_librarian_output("oops")


def test_validate_rejects_missing_key(server):
    bad = {"hard_constraints": [], "summary": "", "recommend_full_read": []}
    assert "concerns" in server._validate_librarian_output(bad)


def test_validate_rejects_hard_constraints_not_list(server):
    bad = {
        "hard_constraints": "not a list",
        "summary": "",
        "recommend_full_read": [],
        "concerns": [],
    }
    assert "hard_constraints is not a list" in server._validate_librarian_output(bad)


def test_validate_rejects_hard_constraint_missing_quote(server):
    bad = {
        "hard_constraints": [{"section": "§1"}],
        "summary": "",
        "recommend_full_read": [],
        "concerns": [],
    }
    assert "quote is missing" in server._validate_librarian_output(bad)


def test_validate_rejects_hard_constraint_empty_quote(server):
    bad = {
        "hard_constraints": [{"quote": "", "section": "§1"}],
        "summary": "",
        "recommend_full_read": [],
        "concerns": [],
    }
    err = server._validate_librarian_output(bad)
    assert "quote" in err and "non-empty" in err


def test_validate_rejects_summary_not_string(server):
    bad = {
        "hard_constraints": [],
        "summary": 42,
        "recommend_full_read": [],
        "concerns": [],
    }
    assert "summary is not a string" in server._validate_librarian_output(bad)


def test_validate_allows_extra_keys(server):
    """Forward compatibility: unknown extra keys are silently ignored."""
    valid = {
        "hard_constraints": [],
        "summary": "",
        "recommend_full_read": [],
        "concerns": [],
        "future_field": "ignored",
    }
    assert server._validate_librarian_output(valid) is None


# ============================================================
# librarian_handler — input validation paths
# ============================================================


def _parse_error(result):
    """Extract the error envelope from a handler's TextContent return."""
    assert len(result) == 1
    return json.loads(result[0].text)


def test_librarian_rejects_when_neither_input_provided(server):
    result = asyncio.run(server.librarian_handler({"query": "anything"}))
    err = _parse_error(result)
    assert err["error"] == "input_validation"
    assert "exactly one" in err["message"]


def test_librarian_rejects_when_both_inputs_provided(server, tmp_path):
    f = tmp_path / "doc.md"
    f.write_text("hello", encoding="utf-8")
    result = asyncio.run(
        server.librarian_handler(
            {"file_path": str(f), "document_text": "hello", "query": "x"}
        )
    )
    err = _parse_error(result)
    assert err["error"] == "input_validation"


def test_librarian_rejects_missing_query(server):
    result = asyncio.run(server.librarian_handler({"document_text": "hi"}))
    err = _parse_error(result)
    assert err["error"] == "input_validation"
    assert "query" in err["message"]


def test_librarian_rejects_missing_file(server, tmp_path):
    missing = tmp_path / "nope.md"
    result = asyncio.run(
        server.librarian_handler({"file_path": str(missing), "query": "x"})
    )
    err = _parse_error(result)
    assert err["error"] == "file_not_found"


def test_librarian_rejects_oversize_document(server):
    huge = "x" * 100_000  # exceeds default MAX_DOCUMENT_CHARS = 80000
    result = asyncio.run(
        server.librarian_handler({"document_text": huge, "query": "x"})
    )
    err = _parse_error(result)
    assert err["error"] == "document_too_large"


# ============================================================
# librarian_handler — happy path with mocked DeepSeek client
# ============================================================


def _mock_deepseek_response(content: str):
    """Build an object with the shape the handler expects from the SDK."""
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = MagicMock(prompt_tokens=10, completion_tokens=20, total_tokens=30)
    return resp


def test_librarian_happy_path_with_inline_text(server, monkeypatch):
    valid_output = {
        "hard_constraints": [{"quote": "must Y", "section": "§A"}],
        "summary": "summary text",
        "recommend_full_read": [],
        "concerns": [],
    }
    mock_create = AsyncMock(return_value=_mock_deepseek_response(json.dumps(valid_output)))
    monkeypatch.setattr(server.deepseek.chat.completions, "create", mock_create)

    result = asyncio.run(
        server.librarian_handler({"document_text": "doc body", "query": "find Y"})
    )
    assert len(result) == 1
    parsed = json.loads(result[0].text)
    assert parsed == valid_output

    # Verify the request used MODEL_FLASH and JSON response format
    call_kwargs = mock_create.call_args.kwargs
    assert call_kwargs["model"] == server.MODEL_FLASH
    assert call_kwargs["response_format"] == {"type": "json_object"}


def test_librarian_reads_file_and_passes_content_to_model(server, monkeypatch, tmp_path):
    """Worker reads the file directly — orchestrator passes only the path.

    This is the load-bearing token-economy guarantee of the role.
    """
    doc = tmp_path / "design.md"
    doc.write_text("hard constraint line 42", encoding="utf-8")

    valid_output = {
        "hard_constraints": [{"quote": "hard constraint line 42", "section": "§1"}],
        "summary": "",
        "recommend_full_read": [],
        "concerns": [],
    }
    mock_create = AsyncMock(return_value=_mock_deepseek_response(json.dumps(valid_output)))
    monkeypatch.setattr(server.deepseek.chat.completions, "create", mock_create)

    asyncio.run(server.librarian_handler({"file_path": str(doc), "query": "find 42"}))

    # The user message to the model should contain the file's content.
    user_msg = mock_create.call_args.kwargs["messages"][1]["content"]
    assert "hard constraint line 42" in user_msg


def test_librarian_returns_error_when_model_response_is_not_json(server, monkeypatch):
    mock_create = AsyncMock(return_value=_mock_deepseek_response("not valid json {{{"))
    monkeypatch.setattr(server.deepseek.chat.completions, "create", mock_create)

    result = asyncio.run(
        server.librarian_handler({"document_text": "x", "query": "x"})
    )
    err = _parse_error(result)
    assert err["error"] == "output_not_json"


def test_librarian_returns_error_when_output_schema_invalid(server, monkeypatch):
    invalid_output = {"hard_constraints": "should be list"}
    mock_create = AsyncMock(return_value=_mock_deepseek_response(json.dumps(invalid_output)))
    monkeypatch.setattr(server.deepseek.chat.completions, "create", mock_create)

    result = asyncio.run(
        server.librarian_handler({"document_text": "x", "query": "x"})
    )
    err = _parse_error(result)
    assert err["error"] == "output_schema_invalid"


def test_librarian_returns_error_on_api_exception(server, monkeypatch):
    async def boom(**_kwargs):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(server.deepseek.chat.completions, "create", boom)
    result = asyncio.run(
        server.librarian_handler({"document_text": "x", "query": "x"})
    )
    err = _parse_error(result)
    assert err["error"] == "model_api_error"


# ============================================================
# coder_handler — input validation + model identity
# ============================================================


def test_coder_rejects_missing_spec(server):
    result = asyncio.run(server.coder_handler({"language": "python"}))
    assert "spec" in result[0].text and "required" in result[0].text


def test_coder_rejects_missing_language(server):
    result = asyncio.run(server.coder_handler({"spec": "do X"}))
    assert "language" in result[0].text and "required" in result[0].text


def test_coder_uses_model_pro(server, monkeypatch):
    """The rename also bumped the model — coder must call MODEL_PRO."""
    mock_create = AsyncMock(return_value=_mock_deepseek_response("<output>code</output>"))
    monkeypatch.setattr(server.deepseek.chat.completions, "create", mock_create)

    asyncio.run(server.coder_handler({"spec": "trivial", "language": "python"}))

    assert mock_create.call_args.kwargs["model"] == server.MODEL_PRO
    assert server.MODEL_PRO == "deepseek-v4-pro"


# ============================================================
# call_tool dispatcher — unknown tool
# ============================================================


def test_call_tool_returns_error_for_unknown_tool(server):
    result = asyncio.run(server.call_tool("ghost_role", {}))
    assert "Unknown tool" in result[0].text
    assert "ghost_role" in result[0].text
