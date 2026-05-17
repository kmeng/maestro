"""Tests for T6.1 banner parity: every worker emits the same banner shape.

Coder carries the banner as a plaintext prefix; the three JSON workers
(librarian / reviewer / scribe) carry it as a `_banner` JSON field.
`extract_banner` reads either placement uniformly. The regex below is
the shared parser used by Epic 6's downstream tooling, so it is
asserted directly here.
"""

import asyncio
import importlib.util
import json
import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest


_REPO_ROOT = Path(__file__).resolve().parent.parent
_BOOTSTRAP = _REPO_ROOT / "maestro" / "mcp_server.py"

BANNER_REGEX = re.compile(
    r"^\[(\w+) dispatch — ([\w.\-]+) — ([\d.]+)s — (\d+) tokens\]$"
)


@pytest.fixture(scope="module")
def server():
    spec = importlib.util.spec_from_file_location("maestro_server", _BOOTSTRAP)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _mock_resp(content: str, total_tokens: int = 30):
    """Build a fake DeepSeek response with deterministic usage."""
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = MagicMock(
        prompt_tokens=10, completion_tokens=20, total_tokens=total_tokens
    )
    return resp


def _valid_librarian_output():
    return {
        "hard_constraints": [],
        "summary": "ok",
        "recommend_full_read": [],
        "concerns": [],
    }


def _valid_reviewer_output():
    return {
        "verdict": "pass",
        "findings": [],
        "missed_requirements": [],
        "concerns": [],
    }


def _valid_scribe_output():
    return {
        "commit_message": "feat: x",
        "pr_title": "x",
        "pr_body": "x",
        "concerns": [],
    }


# ============================================================
# extract_banner — the uniform reader
# ============================================================


def test_extract_banner_handles_plaintext_prefix(server):
    """coder-style result_text starts with [...] on the first line."""
    text = "[coder dispatch — deepseek-v4-pro — 1.23s — 100 tokens]\n\nrest of body"
    banner = server.extract_banner(text)
    assert banner == "[coder dispatch — deepseek-v4-pro — 1.23s — 100 tokens]"


def test_extract_banner_handles_json_field(server):
    """librarian/reviewer/scribe-style result_text is JSON with `_banner` field."""
    payload = {
        "_banner": "[reviewer dispatch — deepseek-v4-pro — 2.50s — 200 tokens]",
        "verdict": "pass",
    }
    banner = server.extract_banner(json.dumps(payload))
    assert banner == "[reviewer dispatch — deepseek-v4-pro — 2.50s — 200 tokens]"


def test_extract_banner_returns_none_for_unbannered_text(server):
    """Plain text without banner and without parseable JSON returns None."""
    assert server.extract_banner("just some text without a banner") is None


def test_extract_banner_returns_none_for_json_without_banner_field(server):
    """Error-path responses are JSON but intentionally have no _banner field."""
    payload = {"error": "model_api_error", "message": "boom"}
    assert server.extract_banner(json.dumps(payload)) is None


# ============================================================
# Banner parity across all four workers
# ============================================================


def test_coder_emits_banner_at_start_of_plaintext(server, monkeypatch):
    """Coder retains its plaintext-prefix banner shape after refactor."""
    mock_create = AsyncMock(return_value=_mock_resp("def f(): return 1", total_tokens=42))
    monkeypatch.setattr(server.deepseek.chat.completions, "create", mock_create)

    result = asyncio.run(
        server._coder_impl({"spec": "trivial", "language": "python"})
    )
    text = result[0].text
    banner = server.extract_banner(text)
    assert banner is not None
    m = BANNER_REGEX.match(banner)
    assert m is not None, f"banner did not parse: {banner!r}"
    tool, model, _wall, total = m.groups()
    assert tool == "coder"
    assert model == server.MODEL_PRO
    assert int(total) == 42


@pytest.mark.parametrize(
    "tool_name,impl_attr,expected_model,fixture_factory,call_args",
    [
        (
            "librarian",
            "_librarian_impl",
            "MODEL_FLASH",
            _valid_librarian_output,
            {"document_text": "doc", "query": "q"},
        ),
        (
            "reviewer",
            "_reviewer_impl",
            "MODEL_PRO",
            _valid_reviewer_output,
            {"spec": "s", "code": "def f(): pass", "language": "python"},
        ),
        (
            "scribe",
            "_scribe_impl",
            "MODEL_FLASH",
            _valid_scribe_output,
            {
                "diff": "+x",
                "purpose": "Issue #1 (t): b",
            },
        ),
    ],
)
def test_json_worker_embeds_banner_field(
    server, monkeypatch, tool_name, impl_attr, expected_model, fixture_factory, call_args
):
    """JSON workers expose the banner as a `_banner` field of the parsed payload."""
    output = fixture_factory()
    mock_create = AsyncMock(return_value=_mock_resp(json.dumps(output), total_tokens=77))
    monkeypatch.setattr(server.deepseek.chat.completions, "create", mock_create)

    impl = getattr(server, impl_attr)
    result = asyncio.run(impl(call_args))

    parsed = json.loads(result[0].text)
    assert "_banner" in parsed, f"{tool_name} output missing _banner field"

    banner = server.extract_banner(result[0].text)
    assert banner is not None and banner == parsed["_banner"]

    m = BANNER_REGEX.match(banner)
    assert m is not None, f"banner did not parse: {banner!r}"
    tool, model, _wall, total = m.groups()
    assert tool == tool_name
    assert model == getattr(server, expected_model)
    assert int(total) == 77
