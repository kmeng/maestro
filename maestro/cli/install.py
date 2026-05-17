"""Implementation of `maestro install` — registers Maestro as an MCP server."""

import json
import sys
from pathlib import Path
from typing import Optional


def install(
    config_path: Optional[Path] = None,
    force: bool = False,
    dry_run: bool = False,
) -> int:
    """
    Write or update `~/.claude/mcp.json` to include the maestro MCP server entry.

    Args:
        config_path: Override the default target path. Primarily for testing.
        force: If True, overwrite an existing entry without prompting.
        dry_run: If True, only print what would be done, without writing.

    Returns:
        0 on success (or noop), 1 on error or user decline.
    """
    # 1. Resolve the path to the running binary / entry point
    binary_path = Path(sys.argv[0]).resolve()

    # 2. Resolve target config path
    target = config_path if config_path is not None else Path.home() / ".claude" / "mcp.json"

    # 3. Read existing config (if any)
    file_existed = True
    try:
        with open(target, "r", encoding="utf-8") as fh:
            raw = fh.read()
            if not raw.strip():
                # Treat empty file as missing
                raise FileNotFoundError
            config = json.loads(raw)
    except FileNotFoundError:
        file_existed = False
        config = {"mcpServers": {}}
    except json.JSONDecodeError as exc:
        print(
            f"ERROR: existing config at {target} is not valid JSON: {exc}; refusing to overwrite",
            file=sys.stderr,
        )
        return 1
    except PermissionError as exc:
        print(f"ERROR: cannot read config at {target}: {exc}", file=sys.stderr)
        return 1

    # Ensure mcpServers key exists
    config.setdefault("mcpServers", {})

    # 4. Compute desired maestro entry
    desired = {
        "command": str(binary_path),
        "args": ["serve"],
    }

    mcp_servers = config["mcpServers"]
    existing = mcp_servers.get("maestro")

    # 5. Decide action
    if "maestro" not in mcp_servers:
        action = "add"
    elif existing == desired:
        # Dry-run noop still reports no changes needed
        print(f"maestro install: no changes needed (entry already up to date) at {target}")
        return 0
    else:
        if force:
            action = "overwrite"
        elif dry_run:
            action = "would-overwrite"
        else:
            response = input(f"Overwrite existing maestro entry in {target}? [y/N]: ")
            if response.strip().lower() in ("y", "yes"):
                action = "overwrite"
            else:
                print(
                    f"maestro install: operation declined for {target}.",
                    file=sys.stderr,
                )
                return 1

    # 6. Apply action (dry-run path)
    if dry_run:
        action_text = {
            "add": "Would add maestro entry",
            "overwrite": "Would overwrite maestro entry",
            "would-overwrite": "Would overwrite maestro entry",
        }.get(action, action)
        new_config = config.copy()
        new_config["mcpServers"] = new_config["mcpServers"].copy()
        new_config["mcpServers"]["maestro"] = desired
        print(f"{action_text} at {target}:")
        print(json.dumps(new_config, indent=2))
        return 0

    # 7. Apply action (write path) – only add/overwrite reach here
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"ERROR: cannot create parent directory for {target}: {exc}", file=sys.stderr)
        return 1

    new_config = config.copy()
    new_config["mcpServers"] = new_config["mcpServers"].copy()
    new_config["mcpServers"]["maestro"] = desired

    try:
        with open(target, "w", encoding="utf-8") as fh:
            json.dump(new_config, fh, indent=2)
            fh.write("\n")
    except OSError as exc:
        print(f"ERROR: could not write config at {target}: {exc}", file=sys.stderr)
        return 1

    # Determine summary action word
    if not file_existed:
        action_word = "created"
    elif action == "add":
        action_word = "added maestro entry"
    else:  # overwrite
        action_word = "updated maestro entry"

    print(f"maestro install: {action_word} at {target}; restart Claude Code and run /mcp to verify")
    return 0
