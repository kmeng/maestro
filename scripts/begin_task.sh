#!/usr/bin/env bash
# DEPRECATED (T6.8 / ADR-0011, 2026-05-10). Will be removed in v0.0.4.
# Pass task_id / issue_number as parameters on each worker dispatch
# instead. The git-branch fallback (feature|fix|refactor|docs)/<n>-<slug>
# also covers the common case with zero shell setup.
#
# Source this script (do not execute) to set the current task / issue env vars
# read by the maestro MCP server's dispatch telemetry as a back-compat fallback.
#
# Usage:  source scripts/begin_task.sh T0.4 22

# Reject direct execution; exports only persist if sourced.
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    echo "error: this script must be sourced, not executed" >&2
    echo "usage: source scripts/begin_task.sh <task-id> <issue-number>" >&2
    exit 2
fi

if [ $# -ne 2 ]; then
    echo "usage: source scripts/begin_task.sh <task-id> <issue-number>" >&2
    return 1
fi

export MAESTRO_CURRENT_TASK="$1"
export MAESTRO_CURRENT_ISSUE="$2"
echo "[deprecated] MAESTRO_CURRENT_TASK / MAESTRO_CURRENT_ISSUE will be removed in v0.0.4." >&2
echo "[deprecated] Pass task_id / issue_number as parameters on each worker dispatch instead. See ADR-0011." >&2
echo "MAESTRO_CURRENT_TASK=$MAESTRO_CURRENT_TASK MAESTRO_CURRENT_ISSUE=$MAESTRO_CURRENT_ISSUE"
