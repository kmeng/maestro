#!/usr/bin/env bash
# Source this script (do not execute) to set the current task / issue env vars
# read by the maestro MCP server's dispatch telemetry (Epic 6 / T6.2).
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
echo "MAESTRO_CURRENT_TASK=$MAESTRO_CURRENT_TASK MAESTRO_CURRENT_ISSUE=$MAESTRO_CURRENT_ISSUE"
