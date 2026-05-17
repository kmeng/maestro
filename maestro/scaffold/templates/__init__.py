"""Scaffolding template content as packaged data (T2.4).

The four template files shipped with Maestro are stored under
``maestro/scaffold/templates/`` and read via :mod:`importlib.resources`
so they work correctly for both editable installs and wheels.

CLAUDE.md is special: it has two render forms. The "section body" is the
text BETWEEN ``<!-- maestro:start v=N -->`` and ``<!-- maestro:end v=N -->``
markers and feeds :class:`maestro.scaffold.MergeableFile.section_body`.
The "standalone" form is what we write when CLAUDE.md doesn't exist
yet — markers plus body, end-to-end.

Line endings normalized to LF on read; all renders return ``bytes``.
"""
from __future__ import annotations

from importlib import resources

# Bumped when CLAUDE.md section content materially changes. Older v=N
# blocks then surface as `CONFLICT` (no auto-migration in v0.0.3 per
# ADR-0006).
CURRENT_SECTION_VERSION = 1


def _read_template(name: str) -> str:
    """Read a packaged template file; normalize line endings to LF."""
    raw = (
        resources.files("maestro.scaffold.templates")
        .joinpath(name)
        .read_text(encoding="utf-8")
    )
    return raw.replace("\r\n", "\n").replace("\r", "\n")


def _validate_section_body(body: str) -> None:
    """Raise ValueError if body contains forbidden marker prefixes.

    The forbidden literals are the start/end marker prefixes the
    scaffolding engine uses to delimit Maestro's CLAUDE.md section.
    If body content ever contains them, downstream parsers would
    misidentify section boundaries. See issue #74.
    """
    start_marker_prefix = "<!-- maestro:start v="
    end_marker_prefix = "<!-- maestro:end v="
    if start_marker_prefix in body:
        raise ValueError(
            f"Forbidden start-marker prefix found in section body: "
            f"'{start_marker_prefix}'"
        )
    if end_marker_prefix in body:
        raise ValueError(
            f"Forbidden end-marker prefix found in section body: "
            f"'{end_marker_prefix}'"
        )


def render_claude_md_section_body(
    section_version: int = CURRENT_SECTION_VERSION,
) -> bytes:
    """Return the BODY text that goes between maestro:start/end markers.

    Used by the scaffolding engine's ``MergeableFile.section_body``.
    The body itself does NOT carry the delimiter markers — see
    :func:`render_claude_md_standalone` for the wrapped form.

    ``section_version`` is currently informational only (the body content
    is the same across versions in v0.0.3). It exists so future
    Maestro releases can produce different bodies for different
    delimiter versions.

    Calls :func:`_validate_section_body` on the read template content
    as defense-in-depth — see issue #74. The packaged template is
    sanitization-clean so this is a no-op in v0.0.3.
    """
    # v0.0.3 ships v=1 only; the body is the same regardless of version
    # argument. Parameter accepted for forward compatibility.
    _ = section_version
    body_str = _read_template("claude_md_maestro_section.md")
    _validate_section_body(body_str)
    return body_str.encode("utf-8")


def render_claude_md_standalone(
    section_version: int = CURRENT_SECTION_VERSION,
) -> bytes:
    """Return the FULL CLAUDE.md content (markers + body).

    Used on the CREATE path when CLAUDE.md doesn't exist yet. Output
    shape::

        <!-- maestro:start v=N -->
        {body}
        <!-- maestro:end v=N -->

    Where N is ``section_version`` and ``{body}`` is the section
    template content with no leading or trailing blank lines.
    """
    body = render_claude_md_section_body(section_version).decode("utf-8").strip("\n")
    return (
        f"<!-- maestro:start v={section_version} -->\n"
        f"{body}\n"
        f"<!-- maestro:end v={section_version} -->\n"
    ).encode("utf-8")


def render_readme_stub() -> bytes:
    """Return the Chinese README stub (new-project flow only).

    Contains a literal ``{项目名}`` placeholder the user is expected to
    replace by hand — the renderer does NOT substitute it.
    """
    return _read_template("readme_stub.md").encode("utf-8")


def render_gitignore() -> bytes:
    """Return the project-root .gitignore content (new-project flow only).

    Python defaults plus the ``.maestro/logs/`` directory so worker
    dispatch telemetry stays out of git.
    """
    return _read_template("gitignore").encode("utf-8")


def render_maestro_gitignore() -> bytes:
    """Return the .maestro/.gitignore content — exactly ``logs/`` + newline.

    Used in both new-project and take-over flows. The single line keeps
    logs from being committed even if a user adds the .maestro/ directory
    to their repo's tracked tree.
    """
    return _read_template("maestro_gitignore").encode("utf-8")
