#!/usr/bin/env bash
# Epic 0 automated smoke test.
# Exercises CLI + web server + port-conflict fallback without manual steps.
# Manual portion (browser visual + MCP coder regression) lives in epic0.md.

set -euo pipefail

cd "$(dirname "$0")/../.."

declare -a LOG_FILES=()
LAUNCHER_PID=""
OCCUPY_PID=""

cleanup() {
    if [ -n "${LAUNCHER_PID:-}" ]; then
        kill "$LAUNCHER_PID" 2>/dev/null || true
    fi
    if [ -n "${OCCUPY_PID:-}" ]; then
        kill "$OCCUPY_PID" 2>/dev/null || true
    fi
    if [ "${#LOG_FILES[@]}" -gt 0 ]; then
        for f in "${LOG_FILES[@]}"; do
            rm -f "$f" 2>/dev/null || true
        done
    fi
}
trap cleanup EXIT INT TERM

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1" >&2; exit 1; }

# ---------------------------------------
# Check 1: install is current (idempotent)
# ---------------------------------------
pip install -e . -q && pass "install is current" || fail "pip install failed"

# ---------------------------------------
# Check 2: maestro-webui console_script exists
# ---------------------------------------
command -v maestro-webui >/dev/null && pass "maestro-webui console_script exists" \
    || fail "maestro-webui not found; re-run check 1"

# ---------------------------------------
# Check 3: launcher starts and prints URL
# ---------------------------------------
LOG_FILE=$(mktemp /tmp/epic0_smoke.XXXXXX)
LOG_FILES+=("$LOG_FILE")
maestro-webui > "$LOG_FILE" 2>&1 &
LAUNCHER_PID=$!

URL=""
for i in {1..20}; do
    sleep 0.5
    if grep -qE 'http://127\.0\.0\.1:[0-9]+' "$LOG_FILE"; then
        URL=$(grep -Eo 'http://127\.0\.0\.1:[0-9]+' "$LOG_FILE" | head -n1)
        break
    fi
done

if [ -z "$URL" ]; then
    echo "Launcher log:" >&2
    cat "$LOG_FILE" >&2
    fail "launcher did not output URL within 10 seconds"
fi
pass "launcher started and printed URL ($URL)"

# ---------------------------------------
# Check 4: GET / returns 200 with Chinese hero copy
# ---------------------------------------
if curl -fsS "$URL/" | grep -q "等待第一支乐章"; then
    pass "GET / returns Chinese hero copy"
else
    fail "Chinese hero copy not found on /"
fi

# ---------------------------------------
# Check 5: GET /static/vendor/htmx.min.js returns 200
# ---------------------------------------
if curl -fsS -o /dev/null "$URL/static/vendor/htmx.min.js"; then
    pass "GET /static/vendor/htmx.min.js returns 200"
else
    fail "htmx.min.js not served"
fi

# ---------------------------------------
# Check 6: GET /health returns {"status":"ok"}
# ---------------------------------------
if curl -fsS "$URL/health" | grep -q '"status":"ok"'; then
    pass "GET /health returns {\"status\":\"ok\"}"
else
    fail "health endpoint mismatch"
fi

# ---------------------------------------
# Check 7: kill launcher cleanly, port is freed
# ---------------------------------------
PORT="${URL##*:}"
kill "$LAUNCHER_PID" 2>/dev/null || true
LAUNCHER_PID=""
sleep 1

if python3 -c "import socket; s=socket.socket(); s.bind(('127.0.0.1', $PORT)); s.close()" 2>/dev/null; then
    pass "port $PORT freed after kill"
else
    fail "port $PORT still in use after killing launcher"
fi

# ---------------------------------------
# Check 8: port-conflict fallback (occupy 19830, expect bind to 19831)
# ---------------------------------------
python3 -c "
import socket, time
s = socket.socket()
s.bind(('127.0.0.1', 19830))
s.listen(1)
time.sleep(60)
" &
OCCUPY_PID=$!
sleep 1

LOG_FILE2=$(mktemp /tmp/epic0_smoke.XXXXXX)
LOG_FILES+=("$LOG_FILE2")
maestro-webui > "$LOG_FILE2" 2>&1 &
LAUNCHER_PID=$!

URL2=""
for i in {1..20}; do
    sleep 0.5
    if grep -qE 'http://127\.0\.0\.1:[0-9]+' "$LOG_FILE2"; then
        URL2=$(grep -Eo 'http://127\.0\.0\.1:[0-9]+' "$LOG_FILE2" | head -n1)
        break
    fi
done

if [ -z "$URL2" ] || [ "$URL2" != "http://127.0.0.1:19831" ]; then
    echo "Launcher log(s):" >&2
    cat "$LOG_FILE2" >&2
    fail "fallback URL mismatch. Expected http://127.0.0.1:19831, got ${URL2:-none}"
fi

kill "$LAUNCHER_PID" 2>/dev/null || true; LAUNCHER_PID=""
kill "$OCCUPY_PID" 2>/dev/null || true; OCCUPY_PID=""
pass "port-conflict fallback to 19831 works"

# ---------------------------------------
# All automated checks passed
# ---------------------------------------
echo
echo "ALL AUTOMATED CHECKS PASSED"
exit 0
