import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence


def _cmd_serve(_args: argparse.Namespace) -> int:
    """Launch the MCP server on stdio. Blocks until shutdown."""
    from maestro.mcp_server import run_stdio

    run_stdio()
    return 0


def _cmd_webui(forwarded_argv: list) -> int:
    from maestro.webui.launcher import main as webui_main

    return webui_main(forwarded_argv)


def _cmd_install(args: argparse.Namespace) -> int:
    from maestro.cli.install import install

    config_path = Path(args.config_path) if args.config_path else None
    return install(
        config_path=config_path,
        force=args.force,
        dry_run=args.dry_run,
    )


def _cmd_version() -> int:
    try:
        from maestro import __version__ as version
    except ImportError:
        # Defensive fallback — should never trigger in practice since the
        # CLI lives INSIDE the maestro package.
        from importlib import metadata

        version = metadata.version("maestro")
    print(f"maestro {version}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="maestro",
        description="Maestro — orchestrate a heterogeneous AI software team via MCP.",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print the installed maestro version and exit.",
    )
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("serve", help="Start the MCP server on stdio (for Claude Code).")

    sub.add_parser(
        "webui",
        help="Start the Maestro Web UI.",
        add_help=False,  # let the webui launcher own its --help text
    )
    # No REMAINDER argument; unknown args will be captured via parse_known_args.

    install_p = sub.add_parser(
        "install", help="Register Maestro with Claude Code (writes ~/.claude/mcp.json)."
    )
    install_p.add_argument(
        "--force", action="store_true",
        help="Overwrite an existing maestro entry without prompting.",
    )
    install_p.add_argument(
        "--config-path", default=None,
        help="Override target config path (default: ~/.claude/mcp.json).",
    )
    install_p.add_argument(
        "--dry-run", action="store_true",
        help="Show what would change without writing the file.",
    )

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args, unknown = parser.parse_known_args(argv)

    if args.version:
        if unknown:
            parser.error(f"unrecognized arguments: {' '.join(unknown)}")
        return _cmd_version()

    if args.cmd == "serve":
        if unknown:
            parser.error(f"unrecognized arguments: {' '.join(unknown)}")
        return _cmd_serve(args)

    if args.cmd == "webui":
        # webui forwards ALL unknown args (including --port etc.) to the
        # webui launcher's own argparse. This is the only subcommand that
        # accepts unknown args without erroring.
        return _cmd_webui(unknown)

    if args.cmd == "install":
        if unknown:
            parser.error(f"unrecognized arguments: {' '.join(unknown)}")
        return _cmd_install(args)

    if unknown:
        parser.error(f"unrecognized arguments: {' '.join(unknown)}")
    parser.print_help(sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
