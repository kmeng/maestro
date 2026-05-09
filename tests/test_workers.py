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


def test_tools_registry_contains_all_four_roles(server):
    assert set(server.TOOLS_REGISTRY.keys()) == {"coder", "librarian", "reviewer", "scribe"}


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
    """Verbatim quotes survive the verifier and reach the caller intact."""
    document = "the system must Y in all cases"
    valid_output = {
        "hard_constraints": [{"quote": "must Y", "section": "§A"}],
        "summary": "summary text",
        "recommend_full_read": [],
        "concerns": [],
    }
    mock_create = AsyncMock(return_value=_mock_deepseek_response(json.dumps(valid_output)))
    monkeypatch.setattr(server.deepseek.chat.completions, "create", mock_create)

    result = asyncio.run(
        server.librarian_handler({"document_text": document, "query": "find Y"})
    )
    assert len(result) == 1
    parsed = json.loads(result[0].text)
    assert parsed == valid_output

    # Verify the request used MODEL_FLASH and JSON response format
    call_kwargs = mock_create.call_args.kwargs
    assert call_kwargs["model"] == server.MODEL_FLASH
    assert call_kwargs["response_format"] == {"type": "json_object"}


def test_librarian_resolves_relative_path_against_project_root(server, monkeypatch):
    """Relative file_path resolves to repo root, not server CWD.

    The MCP server's CWD is the launching client's working directory
    (often unrelated to the repo); without this resolution, callers would
    have to pass absolute paths for every doc — defeating ergonomics.
    """
    valid_output = {
        "hard_constraints": [],
        "summary": "",
        "recommend_full_read": [],
        "concerns": [],
    }
    mock_create = AsyncMock(return_value=_mock_deepseek_response(json.dumps(valid_output)))
    monkeypatch.setattr(server.deepseek.chat.completions, "create", mock_create)

    # README.md is committed at the repo root and exists under any clone.
    result = asyncio.run(
        server.librarian_handler({"file_path": "README.md", "query": "x"})
    )
    # Should NOT be a file_not_found error.
    parsed = json.loads(result[0].text)
    assert "error" not in parsed or parsed.get("error") != "file_not_found"


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
# _verify_verbatim_quotes — verbatim contract enforcement
# ============================================================


def test_verify_accepts_exact_match(server):
    source = "the quick brown fox jumps over the lazy dog"
    quotes = [{"quote": "quick brown fox", "section": "§1"}]
    kept, violations = server._verify_verbatim_quotes(quotes, source)
    assert len(kept) == 1
    assert violations == []


def test_verify_accepts_whitespace_normalized_match(server):
    """Line wraps in source vs single-line quote should still match."""
    source = "the quick brown fox\n  jumps over the lazy dog"
    quotes = [{"quote": "quick brown fox jumps over", "section": "§1"}]
    kept, violations = server._verify_verbatim_quotes(quotes, source)
    assert len(kept) == 1
    assert violations == []


def test_verify_accepts_markdown_stripped(server):
    """Worker may drop **bold** markers — verifier strips them on both sides.

    This is the calibrated behavior per ADR-0008 § Verbatim verification:
    bold is rendering, not content. v4-flash systematically drops `**`
    from prose quotes; rejecting these would produce ~0% hit rate
    without any actual contract value.
    """
    source = "**Role-keyed map** enforces 1 role : 1 member"
    quotes = [{"quote": "Role-keyed map enforces 1 role : 1 member", "section": "§1"}]
    kept, violations = server._verify_verbatim_quotes(quotes, source)
    assert len(kept) == 1
    assert violations == []


def test_verify_accepts_either_with_or_without_bold(server):
    """Worker can preserve `**` or strip it — both pass."""
    source = "**A** is bold and B is plain"
    quotes = [
        {"quote": "**A** is bold", "section": "§1"},  # preserves bold
        {"quote": "A is bold", "section": "§2"},      # strips bold
    ]
    kept, violations = server._verify_verbatim_quotes(quotes, source)
    assert len(kept) == 2
    assert violations == []


def test_verify_rejects_paraphrase(server):
    """Adding punctuation or dropping a leading word is still a contract violation."""
    source = "plus a DEFAULT_MODELS constant sourced from architecture.md"
    quotes = [{"quote": "DEFAULT_MODELS constant sourced from architecture.md.", "section": "§T1.1"}]
    kept, violations = server._verify_verbatim_quotes(quotes, source)
    assert kept == []
    assert len(violations) == 1


def test_verify_rejects_word_substitution(server):
    """Substituting a word — even a synonym — is a contract violation."""
    source = "the system must validate inputs before processing"
    quotes = [{"quote": "the system must check inputs before processing", "section": "§1"}]
    kept, violations = server._verify_verbatim_quotes(quotes, source)
    assert kept == []
    assert len(violations) == 1


def test_verify_rejects_backtick_difference(server):
    """Backticks carry semantic signal (literal identifier vs English word)."""
    source = "the `pm` role is required"
    quotes = [{"quote": "the pm role is required", "section": "§1"}]
    kept, violations = server._verify_verbatim_quotes(quotes, source)
    assert kept == []
    assert len(violations) == 1


def test_verify_preserves_underscore_identifiers(server):
    """`__init__`-style identifiers must not be mangled by the verifier."""
    source = "use `__init__` to set up the instance"
    quotes = [{"quote": "use `__init__` to set up the instance", "section": "§1"}]
    kept, violations = server._verify_verbatim_quotes(quotes, source)
    assert len(kept) == 1
    assert violations == []


def test_verify_rejects_empty_quote(server):
    source = "any source"
    quotes = [{"quote": "", "section": "§1"}]
    kept, violations = server._verify_verbatim_quotes(quotes, source)
    assert kept == []
    assert len(violations) == 1


def test_verify_mixes_pass_and_fail(server):
    source = "**A** is bold and B is plain and C was original"
    quotes = [
        {"quote": "B is plain", "section": "§1"},               # pass
        {"quote": "A is bold", "section": "§2"},                # pass (markdown stripped)
        {"quote": "**A** is bold", "section": "§3"},            # pass (preserved markdown)
        {"quote": "C is original", "section": "§4"},            # fail (was → is)
    ]
    kept, violations = server._verify_verbatim_quotes(quotes, source)
    assert len(kept) == 3
    assert {hc["section"] for hc in kept} == {"§1", "§2", "§3"}
    assert len(violations) == 1
    assert "§4" in violations[0]


def test_librarian_drops_non_verbatim_and_reports_in_concerns(server, monkeypatch):
    """End-to-end: handler runs verifier and reports dropped quotes.

    The first quote is a word-level violation (substituted "the" with "a")
    and gets dropped. The second is verbatim and kept. Confirms the
    handler integrates the verifier and surfaces violations to the
    caller via concerns.
    """
    source_doc = "**Bold X** is a thing.\nA second statement appears here."
    output = {
        "hard_constraints": [
            {"quote": "X is the thing.", "section": "§A"},                    # fail (word change: "a" → "the")
            {"quote": "A second statement appears here.", "section": "§B"},   # pass
        ],
        "summary": "two things",
        "recommend_full_read": [],
        "concerns": ["original concern"],
    }
    mock_create = AsyncMock(return_value=_mock_deepseek_response(json.dumps(output)))
    monkeypatch.setattr(server.deepseek.chat.completions, "create", mock_create)

    result = asyncio.run(
        server.librarian_handler({"document_text": source_doc, "query": "extract things"})
    )
    parsed = json.loads(result[0].text)

    # Only the verbatim quote survived.
    assert len(parsed["hard_constraints"]) == 1
    assert parsed["hard_constraints"][0]["section"] == "§B"

    # Concerns has a summary note + the violation line + original concern.
    assert any("dropped 1 non-verbatim" in c for c in parsed["concerns"])
    assert any("§A" in c for c in parsed["concerns"])
    assert "original concern" in parsed["concerns"]


# ============================================================
# reviewer
# ============================================================


def test_reviewer_tool_required_fields(server):
    assert set(server.REVIEWER_TOOL.inputSchema["required"]) == {"spec", "code", "language"}


def test_validate_reviewer_accepts_valid(server):
    valid = {
        "verdict": "pass",
        "findings": [
            {"severity": "low", "location": "fn foo", "description": "minor"},
        ],
        "missed_requirements": [],
        "concerns": [],
    }
    assert server._validate_reviewer_output(valid) is None


def test_validate_reviewer_rejects_unknown_verdict(server):
    bad = {"verdict": "approved", "findings": [], "missed_requirements": [], "concerns": []}
    err = server._validate_reviewer_output(bad)
    assert err is not None and "verdict" in err


def test_validate_reviewer_rejects_unknown_severity(server):
    bad = {
        "verdict": "concerns",
        "findings": [{"severity": "critical", "location": "x", "description": "y"}],
        "missed_requirements": [],
        "concerns": [],
    }
    err = server._validate_reviewer_output(bad)
    assert err is not None and "severity" in err


def test_validate_reviewer_rejects_finding_missing_location(server):
    bad = {
        "verdict": "fail",
        "findings": [{"severity": "high", "description": "y"}],
        "missed_requirements": [],
        "concerns": [],
    }
    err = server._validate_reviewer_output(bad)
    assert "location" in err


def test_reviewer_rejects_missing_inputs(server):
    result = asyncio.run(server.reviewer_handler({"spec": "x"}))
    err = _parse_error(result)
    assert err["error"] == "input_validation"


def test_reviewer_happy_path_uses_pro(server, monkeypatch):
    """Reviewer is judgment-heavy and must dispatch to MODEL_PRO."""
    valid_output = {
        "verdict": "pass",
        "findings": [],
        "missed_requirements": [],
        "concerns": [],
    }
    mock_create = AsyncMock(return_value=_mock_deepseek_response(json.dumps(valid_output)))
    monkeypatch.setattr(server.deepseek.chat.completions, "create", mock_create)

    result = asyncio.run(
        server.reviewer_handler({"spec": "do X", "code": "def x(): pass", "language": "python"})
    )
    parsed = json.loads(result[0].text)
    assert parsed == valid_output
    assert mock_create.call_args.kwargs["model"] == server.MODEL_PRO


def test_reviewer_returns_error_when_output_schema_invalid(server, monkeypatch):
    bad_output = {"verdict": "yes", "findings": [], "missed_requirements": [], "concerns": []}
    mock_create = AsyncMock(return_value=_mock_deepseek_response(json.dumps(bad_output)))
    monkeypatch.setattr(server.deepseek.chat.completions, "create", mock_create)

    result = asyncio.run(
        server.reviewer_handler({"spec": "x", "code": "y", "language": "python"})
    )
    err = _parse_error(result)
    assert err["error"] == "output_schema_invalid"


# ============================================================
# scribe
# ============================================================


def test_scribe_tool_required_fields(server):
    assert set(server.SCRIBE_TOOL.inputSchema["required"]) == {
        "diff",
        "issue_number",
        "issue_title",
        "issue_body",
        "convention",
    }


def test_validate_scribe_accepts_valid(server):
    valid = {
        "commit_message": "feat: add X",
        "pr_title": "Add X",
        "pr_body": "## Summary\nAdds X.",
        "concerns": [],
    }
    assert server._validate_scribe_output(valid) is None


def test_validate_scribe_rejects_empty_commit_message(server):
    bad = {"commit_message": "", "pr_title": "X", "pr_body": "", "concerns": []}
    err = server._validate_scribe_output(bad)
    assert "commit_message" in err


def test_validate_scribe_rejects_non_string_pr_body(server):
    bad = {"commit_message": "x", "pr_title": "y", "pr_body": 42, "concerns": []}
    err = server._validate_scribe_output(bad)
    assert "pr_body" in err


def test_scribe_rejects_missing_diff(server):
    result = asyncio.run(server.scribe_handler({
        "issue_number": 1,
        "issue_title": "x",
        "issue_body": "y",
        "convention": "z",
    }))
    err = _parse_error(result)
    assert err["error"] == "input_validation"
    assert "diff" in err["message"]


def test_scribe_rejects_non_integer_issue_number(server):
    result = asyncio.run(server.scribe_handler({
        "diff": "x",
        "issue_number": "1",  # string instead of int
        "issue_title": "x",
        "issue_body": "",
        "convention": "x",
    }))
    err = _parse_error(result)
    assert err["error"] == "input_validation"
    assert "issue_number" in err["message"]


def test_scribe_happy_path_uses_flash(server, monkeypatch):
    """Scribe is routine drafting — flash is sufficient."""
    valid_output = {
        "commit_message": "feat(#1): add Y",
        "pr_title": "Add Y",
        "pr_body": "Adds Y.",
        "concerns": [],
    }
    mock_create = AsyncMock(return_value=_mock_deepseek_response(json.dumps(valid_output)))
    monkeypatch.setattr(server.deepseek.chat.completions, "create", mock_create)

    result = asyncio.run(server.scribe_handler({
        "diff": "+ added Y",
        "issue_number": 1,
        "issue_title": "Add Y",
        "issue_body": "We need Y.",
        "convention": "Conventional Commits.",
    }))
    parsed = json.loads(result[0].text)
    assert parsed == valid_output
    assert mock_create.call_args.kwargs["model"] == server.MODEL_FLASH


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
