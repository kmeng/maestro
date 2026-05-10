#!/usr/bin/env python3
"""Dev-only stub: append a placeholder dispatch event to a project's log.

Real event schema lands in Epic 3 T3.1 — this stub exists so Web UI
development (Epics 1–2) has something to read while building screens.

Usage:
    scripts/dev_emit_dispatch.py --project <path> [--success | --failure]

Effect:
    Ensures <project>/.maestro/logs/ exists, appends one JSON line to
    dispatch.jsonl. Each invocation appends one event.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure repo root is on sys.path so `from maestro import paths` works
# regardless of CWD.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from maestro import paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit a stub dispatch event")
    parser.add_argument(
        "--project",
        required=True,
        type=Path,
        help="Path to project root (must exist and be a directory)",
    )
    outcome_group = parser.add_mutually_exclusive_group()
    outcome_group.add_argument(
        "--success",
        action="store_true",
        default=True,
        help="Record success outcome (default)",
    )
    outcome_group.add_argument(
        "--failure",
        action="store_true",
        help="Record failure outcome",
    )
    args = parser.parse_args(argv)

    if not args.project.is_dir():
        print(
            f"error: project path does not exist or is not a directory: {args.project}",
            file=sys.stderr,
        )
        return 1

    logs_dir = paths.dispatch_log_path(args.project)
    logs_dir.mkdir(parents=True, exist_ok=True)

    outcome = "failure" if args.failure else "success"
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "outcome": outcome,
        "tool": "dev_emit_dispatch",
        "note": "stub event awaiting Epic 3 T3.1 schema",
    }

    log_file = logs_dir / "dispatch.jsonl"
    with open(log_file, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(event) + "\n")

    print(f"emitted {event['outcome']} event to {log_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
