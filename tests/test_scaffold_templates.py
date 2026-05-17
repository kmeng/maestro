"""Unit tests for scaffolding template renderers (T2.4)."""
from __future__ import annotations

import pytest

from maestro.scaffold.templates import (
    render_claude_md_section_body,
    render_claude_md_standalone,
    render_readme_stub,
    render_gitignore,
    render_maestro_gitignore,
)


def test_all_four_renderers_return_nonempty_bytes():
    """Every public render_* returns non-empty bytes."""
    assert len(render_claude_md_section_body()) > 0
    assert len(render_claude_md_standalone()) > 0
    assert len(render_readme_stub()) > 0
    assert len(render_gitignore()) > 0
    assert len(render_maestro_gitignore()) > 0


def test_render_is_byte_stable_across_calls():
    """Same input → same bytes across calls (no time / random in output)."""
    assert render_claude_md_section_body() == render_claude_md_section_body()
    assert render_claude_md_standalone() == render_claude_md_standalone()
    assert render_gitignore() == render_gitignore()


def test_claude_md_section_body_is_english():
    """Claude Code is the reader — section body must be English."""
    body = render_claude_md_section_body().decode("utf-8")
    assert "Maestro" in body
    assert "Architect" in body
    assert "MCP tools" in body
    # No CJK ideographs.
    for ch in body:
        assert not ("一" <= ch <= "鿿"), f"Unexpected Chinese char: {ch!r}"


def test_claude_md_standalone_wraps_body_with_v1_markers():
    """Default render wraps the body in v=1 delimiters."""
    standalone = render_claude_md_standalone()
    assert standalone.startswith(b"<!-- maestro:start v=1 -->\n")
    assert standalone.endswith(b"<!-- maestro:end v=1 -->\n")

    inner = standalone[
        len(b"<!-- maestro:start v=1 -->\n"):-len(b"<!-- maestro:end v=1 -->\n")
    ]
    body = render_claude_md_section_body()
    # inner is body content stripped of trailing newlines + wrapper's "\n"
    assert inner.rstrip(b"\n") == body.rstrip(b"\n")


def test_claude_md_standalone_with_explicit_version_substitutes():
    """Explicit version parameter substitutes into both markers — proves
    the wrapper is parameterized for future migration (v=1 → v=2)."""
    v2 = render_claude_md_standalone(section_version=2)
    assert v2.startswith(b"<!-- maestro:start v=2 -->\n")
    assert v2.endswith(b"<!-- maestro:end v=2 -->\n")


def test_readme_stub_is_chinese():
    """User is the reader — README is Chinese."""
    content = render_readme_stub().decode("utf-8")
    assert any("一" <= ch <= "鿿" for ch in content)
    assert "Maestro" in content


def test_gitignore_includes_python_defaults():
    content = render_gitignore().decode("utf-8")
    assert "__pycache__" in content
    assert ".venv" in content
    assert ".env" in content
    assert ".maestro/logs/" in content


def test_maestro_gitignore_is_logs_slash():
    """Single line `logs/` + newline — keep dispatch telemetry out of git."""
    assert render_maestro_gitignore() == b"logs/\n"


def test_all_renders_use_lf_line_endings():
    """No CR anywhere in rendered output — output is always LF."""
    for render in (
        render_claude_md_section_body,
        render_claude_md_standalone,
        render_readme_stub,
        render_gitignore,
        render_maestro_gitignore,
    ):
        assert b"\r" not in render()


# T8.7 / #74 — sanitization helper tests


def test_validate_section_body_rejects_start_marker():
    from maestro.scaffold.templates import _validate_section_body
    with pytest.raises(ValueError, match="start-marker prefix"):
        _validate_section_body("some text <!-- maestro:start v=1 --> more")


def test_validate_section_body_rejects_end_marker():
    from maestro.scaffold.templates import _validate_section_body
    with pytest.raises(ValueError, match="end-marker prefix"):
        _validate_section_body("some text <!-- maestro:end v=1 --> more")


def test_validate_section_body_accepts_benign_body():
    from maestro.scaffold.templates import _validate_section_body
    _validate_section_body("benign text with no markers")
