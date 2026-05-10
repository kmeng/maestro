"""Maestro Web UI launcher — port resolution + uvicorn entry point.

Resolves the listening port in priority order:
  1. --port CLI flag (transient override, highest precedence)
  2. ~/.maestro/settings.yaml `port` key (user-persisted preferred port)
  3. Default 19830

When the chosen preferred port is taken, scan +1..+10 and bind to the
first free one. If all 11 are taken, exit with a clear message that
includes a `--port N` hint.
"""

import argparse
import socket
import sys
from typing import Optional, Sequence

import uvicorn
import yaml

from maestro import paths

DEFAULT_PORT: int = 19830
SCAN_RANGE: int = 10


def read_preferred_port() -> int:
    """Read the preferred port from the user settings file, falling back to DEFAULT_PORT on any error."""
    settings_path = paths.user_settings_path()
    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (OSError, yaml.YAMLError):
        return DEFAULT_PORT
    if not isinstance(data, dict) or "port" not in data:
        return DEFAULT_PORT
    port = data["port"]
    if isinstance(port, int) and port > 0:
        return port
    return DEFAULT_PORT


def _port_is_free(port: int) -> bool:
    """Check if the given port on 127.0.0.1 is available (not in use)."""
    # Bind to 127.0.0.1 to match uvicorn's default host, avoiding accidental exposure.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
        except OSError:
            return False
        return True


def find_free_port(preferred: int, scan_range: int = SCAN_RANGE) -> int:
    """Find the first free port in the range [preferred, preferred+scan_range]."""
    for offset in range(scan_range + 1):
        candidate = preferred + offset
        if _port_is_free(candidate):
            return candidate
    raise RuntimeError(
        f"Ports {preferred}–{preferred + scan_range} are all in use; pass --port N to override."
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Parse CLI args, resolve port, and start uvicorn."""
    parser = argparse.ArgumentParser(description="Maestro Web UI")
    parser.add_argument("--port", type=int, help="Listening port")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    preferred = args.port if args.port is not None else read_preferred_port()
    try:
        port = find_free_port(preferred)
    except RuntimeError as e:
        print(e, file=sys.stderr)
        return 2

    print(f"Maestro Web UI: http://127.0.0.1:{port}")
    uvicorn.run("maestro.webui:app", host="127.0.0.1", port=port, log_level="info")
    return 0
