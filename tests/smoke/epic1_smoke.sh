#!/usr/bin/env bash
# Epic 1 automated smoke test.
# Exercises wizard flow + team catalog + API round-trip + broken-config refusal.
# Manual portion (browser walkthrough + MCP coder dispatches) lives in epic1.md.

set -euo pipefail

cd "$(dirname "$0")/../.."

PROJECT_DIR=""
declare -a LOG_FILES=()
LAUNCHER_PID=""

cleanup() {
    if [ -n "${LAUNCHER_PID:-}" ]; then
        kill "$LAUNCHER_PID" 2>/dev/null || true
    fi
    if [ -n "${PROJECT_DIR:-}" ] && [ -d "$PROJECT_DIR" ]; then
        rm -rf "$PROJECT_DIR" 2>/dev/null || true
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
# Check 2: launcher starts in tmp project dir
# ---------------------------------------
PROJECT_DIR=$(mktemp -d /tmp/epic1_smoke.XXXXXX)
LOG_FILE=$(mktemp /tmp/epic1_smoke.XXXXXX)
LOG_FILES+=("$LOG_FILE")

# Use exec so the subshell IS the maestro-webui process — $! captures uvicorn's
# real PID, not a parent subshell PID that wouldn't propagate kill signals.
(cd "$PROJECT_DIR" && exec maestro-webui > "$LOG_FILE" 2>&1) &
LAUNCHER_PID=$!

URL=""
for i in {1..20}; do
    sleep 0.5
    if grep -qE 'http://127\.0\.0\.1:[0-9]+' "$LOG_FILE"; then
        URL=$(grep -Eo 'http://127\.0\.0\.1:[0-9]+' "$LOG_FILE" | head -n1)
        break
    fi
done
[ -z "$URL" ] && fail "launcher did not output URL"
pass "launcher starts in tmp project dir ($URL)"

# ---------------------------------------
# Check 3: wizard welcome page renders
# ---------------------------------------
curl -fsS "$URL/wizard" | grep -q '下一步' && pass "wizard welcome page renders" || fail "wizard welcome page did not render 下一步"

# ---------------------------------------
# Check 4: wizard step 2 prefills defaults on a fresh project
# ---------------------------------------
STEP2_BODY=$(curl -fsS -X POST "$URL/wizard/step2")
FOUND=0
echo "$STEP2_BODY" | grep -q 'value="Cody"' && FOUND=$((FOUND+1)) || true
echo "$STEP2_BODY" | grep -q 'value="Lily"' && FOUND=$((FOUND+1)) || true
echo "$STEP2_BODY" | grep -q 'value="Rae"'  && FOUND=$((FOUND+1)) || true
echo "$STEP2_BODY" | grep -q 'value="Sage"' && FOUND=$((FOUND+1)) || true
[ "$FOUND" -eq 4 ] && pass "wizard step 2 prefills defaults" || fail "wizard step 2 missing defaults (found $FOUND/4)"

# ---------------------------------------
# Check 5: wizard validate-field rejects invalid model in Chinese
# ---------------------------------------
VF_BODY=$(curl -fsS -X POST "$URL/wizard/validate-field" --data 'role=coder&field=model&value=DeepSeek-V4')
echo "$VF_BODY" | grep -q '格式' && pass "validate-field rejects invalid model" || fail "validate-field did not return Chinese error"

# ---------------------------------------
# Check 6: wizard step 3 accepts valid input
# Form field names: member_<role>, model_<role> (role suffix per template).
# ---------------------------------------
STEP3_BODY=$(curl -fsS -X POST "$URL/wizard/step3" \
  --data 'member_coder=Cody' \
  --data 'model_coder=deepseek-v4-pro' \
  --data 'member_librarian=Lily' \
  --data 'model_librarian=deepseek-v4-flash' \
  --data 'member_reviewer=Rae' \
  --data 'model_reviewer=deepseek-v4-pro' \
  --data 'member_scribe=Sage' \
  --data 'model_scribe=deepseek-v4-flash')
echo "$STEP3_BODY" | grep -q '保存' && pass "wizard step 3 accepts valid input" || fail "wizard step 3 did not show save button"

# ---------------------------------------
# Check 7: wizard save persists team.yaml
# ---------------------------------------
SAVE_BODY=$(curl -fsS -X POST "$URL/wizard/save" \
  --data 'member_coder=Cody' \
  --data 'model_coder=deepseek-v4-pro' \
  --data 'member_librarian=Lily' \
  --data 'model_librarian=deepseek-v4-flash' \
  --data 'member_reviewer=Rae' \
  --data 'model_reviewer=deepseek-v4-pro' \
  --data 'member_scribe=Sage' \
  --data 'model_scribe=deepseek-v4-flash')
echo "$SAVE_BODY" | grep -q '团队组建完成' || fail "wizard save did not show completion message"
[ -f "$PROJECT_DIR/.maestro/team.yaml" ] || fail "team.yaml not created"
pass "wizard save persists team.yaml"

# ---------------------------------------
# Check 8: GET /api/team round-trips the config
# ---------------------------------------
API_RESP=$(curl -fsS "$URL/api/team")
GOT=$(echo "$API_RESP" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d['roles']['coder']['member'])")
[ "$GOT" = "Cody" ] && pass "GET /api/team round-trips config" || fail "GET /api/team returned '$GOT', expected 'Cody'"

# ---------------------------------------
# Check 9: GET /team renders the catalog with saved values
# ---------------------------------------
TEAM_HTML=$(curl -fsS "$URL/team")
echo "$TEAM_HTML" | grep -q 'Claude Code 主会话' || fail "GET /team missing architect row text"
echo "$TEAM_HTML" | grep -q '编码员' || fail "GET /team missing 编码员"
echo "$TEAM_HTML" | grep -q 'Cody' || fail "GET /team missing Cody"
echo "$TEAM_HTML" | grep -q 'deepseek-v4-pro' || fail "GET /team missing deepseek-v4-pro"
pass "GET /team renders catalog with saved values"

# ---------------------------------------
# Check 10: POST /team/edit/coder updates a single row
# ---------------------------------------
EDIT_RESP=$(curl -fsS -X POST "$URL/team/edit/coder" --data 'member=Cody2&model=deepseek-v4-pro')
echo "$EDIT_RESP" | grep -q 'Cody2' || fail "POST /team/edit/coder did not return Cody2"

API_RESP2=$(curl -fsS "$URL/api/team")
GOT2=$(echo "$API_RESP2" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d['roles']['coder']['member'])")
[ "$GOT2" = "Cody2" ] || fail "GET /api/team after edit returned '$GOT2', expected 'Cody2'"
pass "POST /team/edit/coder updates row"

# ---------------------------------------
# Check 11: Hand-broken team.yaml causes GET /api/team to return 422
# ---------------------------------------
echo ': : :' > "$PROJECT_DIR/.maestro/team.yaml"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$URL/api/team")
[ "$HTTP_CODE" = "422" ] && pass "broken team.yaml returns 422" || fail "broken team.yaml returned $HTTP_CODE, expected 422"

# ---------------------------------------
# Check 12: Broken team.yaml causes GET /team to show invalid banner
# ---------------------------------------
TEAM_BROKEN=$(curl -fsS "$URL/team")
echo "$TEAM_BROKEN" | grep -q 'team.yaml 配置无效' && pass "GET /team shows invalid banner" || fail "GET /team did not show invalid banner"

# ---------------------------------------
# Check 13: Restoring valid team.yaml recovers /api/team
# JSON shape per TeamConfig: {schema_version: 1, roles: {<role>: {member, model}}}
# ---------------------------------------
rm -f "$PROJECT_DIR/.maestro/team.yaml"
POST_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$URL/api/team" \
  -H 'Content-Type: application/json' \
  -d '{"schema_version":1,"roles":{"coder":{"member":"Cody","model":"deepseek-v4-pro"},"librarian":{"member":"Lily","model":"deepseek-v4-flash"},"reviewer":{"member":"Rae","model":"deepseek-v4-pro"},"scribe":{"member":"Sage","model":"deepseek-v4-flash"}}}')
[ "$POST_CODE" = "201" ] || fail "POST /api/team restore returned $POST_CODE, expected 201"

RESTORE_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$URL/api/team")
[ "$RESTORE_CODE" = "200" ] || fail "GET /api/team after restore returned $RESTORE_CODE, expected 200"
pass "restoring valid team.yaml recovers /api/team"

# ---------------------------------------
# Check 14: Cleanup — server killed, port freed
# ---------------------------------------
PORT=$(echo "$URL" | grep -Eo '[0-9]+$')
kill "$LAUNCHER_PID" 2>/dev/null || true
wait "$LAUNCHER_PID" 2>/dev/null || true
LAUNCHER_PID=""

# Give the OS up to 5s to release the socket — uvicorn's graceful shutdown
# plus any TCP TIME_WAIT lag (especially on macOS) can hold the port briefly.
for i in {1..10}; do
    sleep 0.5
    if python3 -c "
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    s.bind(('127.0.0.1', $PORT))
    s.close()
except OSError:
    raise SystemExit(1)
" 2>/dev/null; then
        pass "port freed after server kill"
        break
    fi
    [ "$i" -eq 10 ] && fail "port $PORT still occupied after 5s"
done

echo
echo "ALL AUTOMATED CHECKS PASSED"
