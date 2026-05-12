#!/usr/bin/env bash
# Epic 7 自动化验收脚本 (automated portion; manual checklist in epic7.md)
#
# 覆盖 4 状态 per design 65 §2.3:
# - happy:    valid JSONL with measured rows → savings.html
# - missing:  MAESTRO_DISPATCH_LOG → 不存在路径 → savings_empty.html
# - disabled: MAESTRO_DISPATCH_LOG="" → savings_disabled.html
# - error:    MAESTRO_DISPATCH_LOG → 一个目录 → savings_error.html

set -euo pipefail
cd "$(dirname "$0")/../.."

declare -a TMP_DIRS=()
declare -a TMP_FILES=()
declare -a LAUNCHER_PIDS=()

cleanup() {
    # Kill any launchers we started
    for pid in "${LAUNCHER_PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    # Restore permissions on any tmp dirs we chmod'd, so rm -rf doesn't fail
    for d in "${TMP_DIRS[@]}"; do
        chmod -R u+rwX "$d" 2>/dev/null || true
        rm -rf "$d" 2>/dev/null || true
    done
    for f in "${TMP_FILES[@]}"; do
        rm -f "$f" 2>/dev/null || true
    done
}
trap cleanup EXIT INT TERM

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1" >&2; exit 1; }

# Launch the Web UI with an env-injected MAESTRO_DISPATCH_LOG.
# Args: $1 = env value (use the string "UNSET" to leave the var unset;
#       use the string "EMPTY" to set it to ""; otherwise = literal value).
# Returns (via globals): URL, LOG_FILE, LAUNCHER_PID.
launch_with_env() {
    local env_value="$1"
    LOG_FILE=$(mktemp /tmp/epic7_smoke_log.XXXXXX)
    TMP_FILES+=("$LOG_FILE")
    local launcher_dir
    launcher_dir=$(mktemp -d /tmp/epic7_smoke_launcher.XXXXXX)
    TMP_DIRS+=("$launcher_dir")

    if [ "$env_value" = "UNSET" ]; then
        (cd "$launcher_dir" && exec env -u MAESTRO_DISPATCH_LOG maestro-webui > "$LOG_FILE" 2>&1) &
    elif [ "$env_value" = "EMPTY" ]; then
        (cd "$launcher_dir" && MAESTRO_DISPATCH_LOG="" exec maestro-webui > "$LOG_FILE" 2>&1) &
    else
        (cd "$launcher_dir" && MAESTRO_DISPATCH_LOG="$env_value" exec maestro-webui > "$LOG_FILE" 2>&1) &
    fi
    LAUNCHER_PID=$!
    LAUNCHER_PIDS+=("$LAUNCHER_PID")

    # Wait for boot — poll log file for the http://127.0.0.1:<port> URL line.
    URL=""
    for i in {1..30}; do
        sleep 0.5
        local url_try
        url_try=$(grep -Eo 'http://127.0.0.1:[0-9]+' "$LOG_FILE" | head -1 || true)
        if [ -n "$url_try" ] && curl -fsS "$url_try/health" >/dev/null 2>&1; then
            URL="$url_try"
            return 0
        fi
    done
    fail "launcher did not become healthy within 15s; log tail: $(tail -20 "$LOG_FILE")"
}

stop_launcher() {
    if [ -n "${LAUNCHER_PID:-}" ]; then
        kill "$LAUNCHER_PID" 2>/dev/null || true
        wait "$LAUNCHER_PID" 2>/dev/null || true
        LAUNCHER_PID=""
    fi
}

assert_contains() {
    # $1 = haystack, $2 = needle, $3 = label
    if [[ "$1" != *"$2"* ]]; then
        fail "$3: response missing '$2'"
    fi
}

# ----------------------------------------------------------------------
# Check 1: pip install -e . (idempotent, fast on cached env)
pip install -e . >/dev/null 2>&1 || fail "pip install -e . failed"
pass "Check 1: pip install -e . succeeded"

# ----------------------------------------------------------------------
# Check 2: happy state — valid JSONL with 2 rows
HAPPY_LOG=$(mktemp /tmp/epic7_happy_log.XXXXXX.jsonl)
TMP_FILES+=("$HAPPY_LOG")
cat > "$HAPPY_LOG" <<'JSONL'
{"schema_version": 1, "row_id": "smoke-happy-1", "task_id": "T0.1", "issue_number": 1, "tool": "coder", "model": "deepseek-v4-pro", "model_provider": "deepseek", "wall_s": 10.0, "prompt_tokens": 1000, "completion_tokens": 200, "total_tokens": 1200, "started_at": "2026-05-10T08:00:00Z", "journal_ref": null, "is_estimate": false, "est_method": null, "supersedes": null, "error": null}
{"schema_version": 1, "row_id": "smoke-happy-2", "task_id": "T0.2", "issue_number": 2, "tool": "reviewer", "model": "deepseek-v4-pro", "model_provider": "deepseek", "wall_s": 20.0, "prompt_tokens": 500, "completion_tokens": 100, "total_tokens": 600, "started_at": "2026-05-11T15:00:00Z", "journal_ref": null, "is_estimate": false, "est_method": null, "supersedes": null, "error": null}
JSONL

launch_with_env "$HAPPY_LOG"
body=$(curl -fsS "$URL/savings")
assert_contains "$body" "Dispatch Savings" "happy/title"
assert_contains "$body" "Per-role" "happy/per-role section"
assert_contains "$body" "Per-time (UTC day)" "happy/per-time section"
assert_contains "$body" "Reading from:" "happy/footer-path-label"
assert_contains "$body" "$HAPPY_LOG" "happy/footer-path-value"
assert_contains "$body" "Telemetry:" "happy/footer-telemetry-label"
assert_contains "$body" "enabled" "happy/footer-telemetry-state"
assert_contains "$body" "Coder" "happy/role-row-coder"      # capitalized via Jinja
assert_contains "$body" "Reviewer" "happy/role-row-reviewer"
assert_contains "$body" "2026-05-11" "happy/per-time-newest"
assert_contains "$body" "2026-05-10" "happy/per-time-oldest"
stop_launcher
pass "Check 2: happy state renders correctly"

# ----------------------------------------------------------------------
# Check 3: missing state — env points to non-existent path
MISSING_PATH="/tmp/epic7_smoke_no_such_file_$(date +%s).jsonl"
launch_with_env "$MISSING_PATH"
body=$(curl -fsS "$URL/savings")
assert_contains "$body" "No dispatches recorded yet" "missing/heading"
assert_contains "$body" "coder" "missing/role-list-coder"
assert_contains "$body" "librarian" "missing/role-list-librarian"
assert_contains "$body" "reviewer" "missing/role-list-reviewer"
assert_contains "$body" "scribe" "missing/role-list-scribe"
assert_contains "$body" "$MISSING_PATH" "missing/path-surfaced"
stop_launcher
pass "Check 3: missing state renders empty CTA"

# ----------------------------------------------------------------------
# Check 4: disabled state — env=""
launch_with_env "EMPTY"
body=$(curl -fsS "$URL/savings")
assert_contains "$body" "Telemetry is disabled" "disabled/heading"
assert_contains "$body" "MAESTRO_DISPATCH_LOG" "disabled/env-var-name"
assert_contains "$body" "savings-methodology.md" "disabled/methodology-link"
stop_launcher
pass "Check 4: disabled state renders banner"

# ----------------------------------------------------------------------
# Check 5: error state — env points to a directory (read raises IsADirectoryError)
ERROR_DIR=$(mktemp -d /tmp/epic7_smoke_error_dir.XXXXXX)
TMP_DIRS+=("$ERROR_DIR")
launch_with_env "$ERROR_DIR"
body=$(curl -fsS "$URL/savings")
assert_contains "$body" "Could not read the dispatch log" "error/heading"
assert_contains "$body" "$ERROR_DIR" "error/path-surfaced"
# The exception text from Python's IsADirectoryError includes the word "directory"
# in a typical error message ("[Errno 21] Is a directory: ...").
if [[ "$body" != *"directory"* && "$body" != *"Errno"* ]]; then
    fail "error/exception-text: no 'directory' or 'Errno' substring found in error template"
fi
stop_launcher
pass "Check 5: error state renders diagnostic"

# ----------------------------------------------------------------------
echo
echo "ALL CHECKS PASSED — Epic 7 4-state smoke green."
