#!/usr/bin/env python3
"""Deprecated entry point — use the `maestro serve` CLI instead.

This shim exists for users who registered Claude Code against the old
`bootstrap/maestro_server.py` path. New installs should use `maestro install`
which writes a `~/.claude/mcp.json` entry pointing at `maestro serve`.

Importing this module is a no-op (intentionally). Tests that previously
loaded the server via `importlib.spec_from_file_location` against this path
should be updated to `import maestro.mcp_server` directly.
"""

if __name__ == "__main__":
    import sys

    print(
        "WARNING: bootstrap/maestro_server.py is deprecated; use `maestro serve` instead. "
        "Re-register via `maestro install` to migrate.",
        file=sys.stderr,
    )

    from maestro.mcp_server import run_stdio

    run_stdio()
