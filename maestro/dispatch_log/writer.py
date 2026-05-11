"""
Dispatch log writer (T3.2).

Appends events to <project>/.maestro/logs/dispatch.jsonl using POSIX
O_APPEND atomic-write semantics. Rotates by size at 5 MB. Stderr-only
fallback on filesystem error so observability never breaks dispatch.
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from maestro.dispatch_log.events import DispatchEvent
from maestro.dispatch_log.truncation import truncate_event
from maestro.paths import dispatch_log_path

_LOG_FILENAME = "dispatch.jsonl"
_ROTATION_THRESHOLD_BYTES = 5 * 1024 * 1024


def _rotate_if_oversize(log_file: Path) -> None:
    """Rename the current log file to a timestamped archive if it has grown
    past the size threshold, so the next write lands in a fresh file."""
    try:
        size = os.stat(log_file).st_size
    except FileNotFoundError:
        return
    except OSError as e:
        sys.stderr.write(f"maestro: dispatch log stat failed: {e}\n")
        return
    if size <= _ROTATION_THRESHOLD_BYTES:
        return
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive = log_file.with_name(f"dispatch.{ts}.jsonl")
    try:
        os.rename(log_file, archive)
    except OSError as e:
        sys.stderr.write(f"maestro: dispatch log rotate failed: {e}\n")


def emit_event(event: DispatchEvent, project_root: Path) -> None:
    """Append a dispatch event line to the project's dispatch log.

    Side effects:
    - Creates the parent logs directory on first call (or after rotation).
    - Performs size-based rotation in-place before each write when the
      existing file is over 5 MB.

    Never raises on filesystem errors. On any OSError, writes a diagnostic
    to sys.stderr and returns — so logging failure can never fail dispatch."""
    log_dir = dispatch_log_path(project_root)
    log_file = log_dir / _LOG_FILENAME
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        sys.stderr.write(f"maestro: dispatch log mkdir failed: {e}\n")
        return
    _rotate_if_oversize(log_file)
    truncated = truncate_event(event)
    line_bytes = (truncated.model_dump_json() + "\n").encode("utf-8")
    try:
        fd = os.open(str(log_file), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    except OSError as e:
        sys.stderr.write(f"maestro: dispatch log open failed: {e}\n")
        return
    try:
        os.write(fd, line_bytes)
    except OSError as e:
        sys.stderr.write(f"maestro: dispatch log write failed: {e}\n")
    finally:
        try:
            os.close(fd)
        except OSError:
            pass
