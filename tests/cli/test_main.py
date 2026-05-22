"""Tests for maestro/cli/main.py — subcommand routing + version."""

import re
from typing import List

import pytest

import maestro.cli.main as cli_main


def run_cli(args: List[str], capsys) -> tuple[int, str, str]:
    """Helper: invoke cli_main.main(args), return (exit_code, stdout, stderr)."""
    code = cli_main.main(args)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_version_flag_prints_and_exits_zero(capsys):
    code, out, _ = run_cli(["--version"], capsys)
    assert code == 0
    assert re.match(r"^maestro \d+\.\d+\.\d+\S*\n?$", out), f"unexpected stdout: {out!r}"


def test_version_flag_matches_pyproject(capsys):
    from maestro import __version__ as pkg_version
    code, out, _ = run_cli(["--version"], capsys)
    assert code == 0
    assert pkg_version in out


def test_no_args_prints_help_to_stderr_and_exits_nonzero(capsys):
    code, _, err = run_cli([], capsys)
    assert code == 1
    assert "usage: maestro" in err.lower()
    assert "serve" in err
    assert "webui" in err
    assert "install" in err


def test_unknown_subcommand_exits_nonzero(capsys):
    with pytest.raises(SystemExit) as exc:
        run_cli(["nonexistent-subcommand"], capsys)
    assert exc.value.code == 2


def test_serve_subcommand_registered(capsys):
    parser = cli_main._build_parser()
    subs_action = next(a for a in parser._actions if isinstance(a, type(parser._actions[-1])) and hasattr(a, "choices"))
    assert "serve" in subs_action.choices
    assert "webui" in subs_action.choices
    assert "install" in subs_action.choices


def test_webui_subcommand_forwards_remainder():
    parser = cli_main._build_parser()
    args, unknown = parser.parse_known_args(["webui", "--port", "19999"])
    assert args.cmd == "webui"
    assert unknown == ["--port", "19999"]
