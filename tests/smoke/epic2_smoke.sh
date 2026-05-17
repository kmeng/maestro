#!/usr/bin/env bash
# Epic 2 自动化验收脚本 (automated portion; manual portion in epic2.md)
set -euo pipefail
cd "$(dirname "$0")/../.."

declare -a LOG_FILES=()
declare -a TMP_DIRS=()
LAUNCHER_PID=""
URL=""

cleanup() {
    if [ -n "${LAUNCHER_PID:-}" ]; then kill "$LAUNCHER_PID" 2>/dev/null || true; fi
    for d in "${TMP_DIRS[@]}"; do rm -rf "$d" 2>/dev/null || true; done
    for f in "${LOG_FILES[@]}"; do rm -f "$f" 2>/dev/null || true; done
}
trap cleanup EXIT INT TERM

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1" >&2; exit 1; }

# ----------------------------------------------------------------------
# Check 1: pip install -e . is current
pip install -e . >/dev/null 2>&1 || fail "pip install -e . failed"
pass "Check 1: pip install -e . succeeded"

# ----------------------------------------------------------------------
# Check 2: launcher starts in tmp dir; /health responds
LAUNCHER_DIR=$(mktemp -d /tmp/epic2_smoke_launcher.XXXXXX)
TMP_DIRS+=("$LAUNCHER_DIR")
LOG_FILE=$(mktemp /tmp/epic2_smoke_launcher_log.XXXXXX)
LOG_FILES+=("$LOG_FILE")

(cd "$LAUNCHER_DIR" && exec maestro-webui > "$LOG_FILE" 2>&1) &
LAUNCHER_PID=$!

for i in {1..20}; do
    sleep 0.5
    URL_TRY=$(grep -Eo 'http://127.0.0.1:[0-9]+' "$LOG_FILE" | head -1 || true)
    if [ -n "$URL_TRY" ] && curl -fsS "$URL_TRY/health" >/dev/null 2>&1; then
        URL="$URL_TRY"
        break
    fi
done
[ -n "$URL" ] || fail "launcher did not become ready (log: $LOG_FILE)"
pass "Check 2: launcher ready at $URL"

# ----------------------------------------------------------------------
# Check 3: NEW PROJECT plan — all preflight pass, 4 CREATE rows
PLAN_3_DIR=$(mktemp -d /tmp/epic2_smoke_plan_new.XXXXXX)
TMP_DIRS+=("$PLAN_3_DIR")

RESP3=$(curl -fsS -X POST "$URL/api/scaffold/plan" \
    -H "Content-Type: application/json" \
    -d "{\"path\":\"$PLAN_3_DIR\",\"mode\":\"new_project\"}")

PREFLIGHT_COUNT=$(echo "$RESP3" | python3 -c "import sys,json; print(len(json.load(sys.stdin)['preflight']))")
[ "$PREFLIGHT_COUNT" -eq 4 ] || fail "expected 4 preflight checks, got $PREFLIGHT_COUNT"
for idx in 0 1 2 3; do
    PASSED=$(echo "$RESP3" | python3 -c "import sys,json; print(json.load(sys.stdin)['preflight'][$idx]['passed'])")
    [ "$PASSED" = "True" ] || fail "preflight check $idx not passed"
done
ROWS_LEN3=$(echo "$RESP3" | python3 -c "import sys,json; print(len(json.load(sys.stdin)['rows']))")
[ "$ROWS_LEN3" -eq 4 ] || fail "plan rows length expected 4, got $ROWS_LEN3"
for idx in 0 1 2 3; do
    OP=$(echo "$RESP3" | python3 -c "import sys,json; print(json.load(sys.stdin)['rows'][$idx]['op'])")
    [ "$OP" = "CREATE" ] || fail "row $idx op expected CREATE, got $OP"
done
pass "Check 3: new_project plan shape ok"

# ----------------------------------------------------------------------
# Check 4: NEW PROJECT apply — 4 CREATE events + plan_complete + files on disk
ACCEPTED_3=$(echo "$RESP3" | python3 -c "import sys,json; print(json.dumps([r['path'] for r in json.load(sys.stdin)['rows']]))")
SSE_4=$(curl -fsS -N -X POST "$URL/api/scaffold/apply" \
    -H "Content-Type: application/json" \
    -d "{\"path\":\"$PLAN_3_DIR\",\"mode\":\"new_project\",\"accepted_paths\":$ACCEPTED_3}")

SUC_COUNT=$(echo "$SSE_4" | grep -c "^event: file_succeeded" || true)
[ "$SUC_COUNT" -ge 4 ] || fail "expected >=4 file_succeeded events, got $SUC_COUNT"

SUMMARY_4=$(echo "$SSE_4" | grep -A1 "^event: plan_complete" | tail -1)
[ -n "$SUMMARY_4" ] || fail "plan_complete event missing"
SUCCEEDED_4=$(echo "$SUMMARY_4" | python3 -c "import sys,json,re; m=re.match(r'data: (.*)',sys.stdin.read().strip()); print(json.loads(m.group(1))['succeeded'])")
[ "$SUCCEEDED_4" = "4" ] || fail "plan_complete succeeded expected 4, got $SUCCEEDED_4"
FAILED_4=$(echo "$SUMMARY_4" | python3 -c "import sys,json,re; m=re.match(r'data: (.*)',sys.stdin.read().strip()); print(json.loads(m.group(1))['failed'])")
[ "$FAILED_4" = "0" ] || fail "plan_complete failed expected 0, got $FAILED_4"

for f in .gitignore README.md CLAUDE.md .maestro/.gitignore; do
    [ -f "$PLAN_3_DIR/$f" ] || fail "file $f missing after apply"
done
grep -q '<!-- maestro:start v=1 -->' "$PLAN_3_DIR/CLAUDE.md" || fail "CLAUDE.md missing maestro start marker"
grep -q '<!-- maestro:end v=1 -->' "$PLAN_3_DIR/CLAUDE.md" || fail "CLAUDE.md missing maestro end marker"
pass "Check 4: new_project apply ok"

# ----------------------------------------------------------------------
# Check 5: TAKE-OVER PREP — git init + initial commit
REPO_5=$(mktemp -d /tmp/epic2_smoke_repo.XXXXXX)
TMP_DIRS+=("$REPO_5")
git -C "$REPO_5" init >/dev/null 2>&1
git -C "$REPO_5" config user.email "smoke@test"
git -C "$REPO_5" config user.name "Smoke Test"
touch "$REPO_5/initial.txt"
git -C "$REPO_5" add . >/dev/null 2>&1
git -C "$REPO_5" commit -m "initial commit" >/dev/null 2>&1 || fail "git init+commit failed"
pass "Check 5: git repo initialised"

# ----------------------------------------------------------------------
# Check 6: TAKE-OVER plan on clean repo — 2 CREATE rows
RESP6=$(curl -fsS -X POST "$URL/api/scaffold/plan" \
    -H "Content-Type: application/json" \
    -d "{\"path\":\"$REPO_5\",\"mode\":\"take_over\"}")

PREFLIGHT6_COUNT=$(echo "$RESP6" | python3 -c "import sys,json; print(len(json.load(sys.stdin)['preflight']))")
[ "$PREFLIGHT6_COUNT" -eq 4 ] || fail "Check 6 preflight count expected 4, got $PREFLIGHT6_COUNT"
for idx in 0 1 2 3; do
    PASSED=$(echo "$RESP6" | python3 -c "import sys,json; print(json.load(sys.stdin)['preflight'][$idx]['passed'])")
    [ "$PASSED" = "True" ] || fail "Check 6 preflight $idx not passed"
done
ROWS_LEN6=$(echo "$RESP6" | python3 -c "import sys,json; print(len(json.load(sys.stdin)['rows']))")
[ "$ROWS_LEN6" -eq 2 ] || fail "Check 6 rows expected 2, got $ROWS_LEN6"
for idx in 0 1; do
    OP=$(echo "$RESP6" | python3 -c "import sys,json; print(json.load(sys.stdin)['rows'][$idx]['op'])")
    [ "$OP" = "CREATE" ] || fail "Check 6 row $idx op expected CREATE, got $OP"
done
pass "Check 6: take_over plan on clean repo ok"

# ----------------------------------------------------------------------
# Check 7: TAKE-OVER apply — 2 files written, NO internal-project conventions
ACCEPTED_7=$(echo "$RESP6" | python3 -c "import sys,json; print(json.dumps([r['path'] for r in json.load(sys.stdin)['rows']]))")
SSE_7=$(curl -fsS -N -X POST "$URL/api/scaffold/apply" \
    -H "Content-Type: application/json" \
    -d "{\"path\":\"$REPO_5\",\"mode\":\"take_over\",\"accepted_paths\":$ACCEPTED_7}")

SUMMARY_7=$(echo "$SSE_7" | grep -A1 "^event: plan_complete" | tail -1)
[ -n "$SUMMARY_7" ] || fail "Check 7 plan_complete missing"
SUCC_7=$(echo "$SUMMARY_7" | python3 -c "import sys,json,re; m=re.match(r'data: (.*)',sys.stdin.read().strip()); print(json.loads(m.group(1))['succeeded'])")
[ "$SUCC_7" = "2" ] || fail "Check 7 succeeded expected 2, got $SUCC_7"
FAIL_7=$(echo "$SUMMARY_7" | python3 -c "import sys,json,re; m=re.match(r'data: (.*)',sys.stdin.read().strip()); print(json.loads(m.group(1))['failed'])")
[ "$FAIL_7" = "0" ] || fail "Check 7 failed expected 0, got $FAIL_7"

[ -f "$REPO_5/.maestro/.gitignore" ] || fail ".maestro/.gitignore missing after apply"
[ -f "$REPO_5/CLAUDE.md" ] || fail "CLAUDE.md missing after apply"
grep -q '<!-- maestro:start v=1 -->' "$REPO_5/CLAUDE.md" || fail "CLAUDE.md missing start marker"

# Verify take-over does NOT create internal-project convention files (ADR-0005 scope discipline)
[ ! -d "$REPO_5/docs/journal" ] || fail "docs/journal/ should not exist"
[ ! -f "$REPO_5/BUILD_LOG.md" ] || fail "BUILD_LOG.md should not exist"
[ ! -f "$REPO_5/docs/governance.md" ] || fail "docs/governance.md should not exist"
[ ! -f "$REPO_5/docs/architecture.md" ] || fail "docs/architecture.md should not exist"
pass "Check 7: take_over apply ok (no internal-project files leaked)"

# Commit the apply's writes so the tree is clean for the idempotence test.
# In real usage the user commits between take-over runs; clean_tree preflight
# would otherwise block the re-run apply (which is correct behavior).
git -C "$REPO_5" add . >/dev/null 2>&1
git -C "$REPO_5" commit -m "maestro take-over" >/dev/null 2>&1 || fail "post-apply commit failed"

# ----------------------------------------------------------------------
# Check 8: TAKE-OVER IDEMPOTENCE — re-plan shows all NOOP
RESP8=$(curl -fsS -X POST "$URL/api/scaffold/plan" \
    -H "Content-Type: application/json" \
    -d "{\"path\":\"$REPO_5\",\"mode\":\"take_over\"}")

R8_LEN=$(echo "$RESP8" | python3 -c "import sys,json; print(len(json.load(sys.stdin)['rows']))")
[ "$R8_LEN" -eq 2 ] || fail "idempotent plan rows expected 2, got $R8_LEN"
for idx in 0 1; do
    OP=$(echo "$RESP8" | python3 -c "import sys,json; print(json.load(sys.stdin)['rows'][$idx]['op'])")
    [ "$OP" = "NOOP" ] || fail "idempotent row $idx op expected NOOP, got $OP"
done

ACCEPTED_8=$(echo "$RESP8" | python3 -c "import sys,json; print(json.dumps([r['path'] for r in json.load(sys.stdin)['rows']]))")
SSE_8=$(curl -fsS -N -X POST "$URL/api/scaffold/apply" \
    -H "Content-Type: application/json" \
    -d "{\"path\":\"$REPO_5\",\"mode\":\"take_over\",\"accepted_paths\":$ACCEPTED_8}")

SUMMARY_8=$(echo "$SSE_8" | grep -A1 "^event: plan_complete" | tail -1)
SUCC_8=$(echo "$SUMMARY_8" | python3 -c "import sys,json,re; m=re.match(r'data: (.*)',sys.stdin.read().strip()); print(json.loads(m.group(1))['succeeded'])")
[ "$SUCC_8" = "2" ] || fail "idempotent apply succeeded expected 2, got $SUCC_8"
pass "Check 8: take_over idempotence ok"

# ----------------------------------------------------------------------
# Check 9: TAKE-OVER WITH PRE-EXISTING CLAUDE.md — APPEND_DELIMITED preserves user content
REPO_9=$(mktemp -d /tmp/epic2_smoke_repo9.XXXXXX)
TMP_DIRS+=("$REPO_9")
git -C "$REPO_9" init >/dev/null 2>&1
git -C "$REPO_9" config user.email "smoke@test"
git -C "$REPO_9" config user.name "Smoke Test"
cat > "$REPO_9/CLAUDE.md" <<'EOF'
# My Project

My own existing content.
EOF
git -C "$REPO_9" add . >/dev/null 2>&1
git -C "$REPO_9" commit -m "initial with claude" >/dev/null 2>&1

RESP9=$(curl -fsS -X POST "$URL/api/scaffold/plan" \
    -H "Content-Type: application/json" \
    -d "{\"path\":\"$REPO_9\",\"mode\":\"take_over\"}")

OP_CLAUDE_9=$(echo "$RESP9" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for r in d['rows']:
    if r['path'] == 'CLAUDE.md':
        print(r['op'])
        break
")
[ "$OP_CLAUDE_9" = "APPEND_DELIMITED" ] || fail "Check 9 CLAUDE.md op expected APPEND_DELIMITED, got $OP_CLAUDE_9"

ACCEPTED_9=$(echo "$RESP9" | python3 -c "import sys,json; print(json.dumps([r['path'] for r in json.load(sys.stdin)['rows']]))")
SSE_9=$(curl -fsS -N -X POST "$URL/api/scaffold/apply" \
    -H "Content-Type: application/json" \
    -d "{\"path\":\"$REPO_9\",\"mode\":\"take_over\",\"accepted_paths\":$ACCEPTED_9}")
SUMMARY_9=$(echo "$SSE_9" | grep -A1 "^event: plan_complete" | tail -1)
SUCC_9=$(echo "$SUMMARY_9" | python3 -c "import sys,json,re; m=re.match(r'data: (.*)',sys.stdin.read().strip()); print(json.loads(m.group(1))['succeeded'])")
[ "$SUCC_9" = "2" ] || fail "Check 9 apply succeeded expected 2, got $SUCC_9"

# Pre-existing user content preserved at start of file
HEADER=$(head -1 "$REPO_9/CLAUDE.md")
[ "$HEADER" = "# My Project" ] || fail "CLAUDE.md first line expected '# My Project', got '$HEADER'"
grep -q '<!-- maestro:start v=1 -->' "$REPO_9/CLAUDE.md" || fail "CLAUDE.md missing maestro start after append"
pass "Check 9: take_over with pre-existing CLAUDE.md preserved user content + appended section"

# ----------------------------------------------------------------------
# Check 10: TAKE-OVER WITH CUSTOM .maestro/.gitignore — surfaces as CONFLICT
REPO_10=$(mktemp -d /tmp/epic2_smoke_repo10.XXXXXX)
TMP_DIRS+=("$REPO_10")
git -C "$REPO_10" init >/dev/null 2>&1
git -C "$REPO_10" config user.email "smoke@test"
git -C "$REPO_10" config user.name "Smoke Test"
mkdir -p "$REPO_10/.maestro"
echo "user-line" > "$REPO_10/.maestro/.gitignore"
git -C "$REPO_10" add . >/dev/null 2>&1
git -C "$REPO_10" commit -m "custom .maestro/.gitignore" >/dev/null 2>&1

# Note: pre-flight check `no_existing_maestro` will FAIL here (user has unexpected
# content in .maestro/), so we hit the preflight branch first. Plan still
# returns 200 with structured body; check preflight failure shape.
RESP10=$(curl -fsS -X POST "$URL/api/scaffold/plan" \
    -H "Content-Type: application/json" \
    -d "{\"path\":\"$REPO_10\",\"mode\":\"take_over\"}")

# Either: preflight no_existing_maestro fails (because we put user-line there),
# OR: it passes since only .gitignore is the canonical entry — but the byte
# content differs from our template so the engine row should be CONFLICT.
# Both outcomes are spec-compliant; the verification is that the user's custom
# content is surfaced (not silently overwritten). We assert one of them.
PREFLIGHT_NO_MAESTRO=$(echo "$RESP10" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for c in d['preflight']:
    if c['name'] == 'no_existing_maestro':
        print(c['passed'])
        break
")
ROW_CONFLICT=$(echo "$RESP10" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for r in d['rows']:
    if r['path'] == '.maestro/.gitignore' and r['op'] == 'CONFLICT' and r.get('conflict_reason') == 'replacement_differs':
        print('yes')
        sys.exit(0)
print('no')
")
[ "$PREFLIGHT_NO_MAESTRO" = "False" ] || [ "$ROW_CONFLICT" = "yes" ] || \
    fail "Check 10 expected either no_existing_maestro=False OR .maestro/.gitignore=CONFLICT; got preflight=$PREFLIGHT_NO_MAESTRO row_conflict=$ROW_CONFLICT"
pass "Check 10: custom .maestro/.gitignore surfaces (no silent overwrite)"

# ----------------------------------------------------------------------
# Check 11: preflight failure shape on populated non-git dir + new_project mode
POPULATED_DIR=$(mktemp -d /tmp/epic2_smoke_populated.XXXXXX)
TMP_DIRS+=("$POPULATED_DIR")
touch "$POPULATED_DIR/somefile.txt"

RESP11=$(curl -fsS -X POST "$URL/api/scaffold/plan" \
    -H "Content-Type: application/json" \
    -d "{\"path\":\"$POPULATED_DIR\",\"mode\":\"new_project\"}")

ANY_FAILED=$(echo "$RESP11" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('yes' if any(not c['passed'] for c in d['preflight']) else 'no')
")
[ "$ANY_FAILED" = "yes" ] || fail "Check 11 expected at least one preflight to fail on populated new_project dir"
pass "Check 11: preflight failure shape correct"

# ----------------------------------------------------------------------
# Check 12: V0.0.2 REGRESSION — bootstrap MCP server module imports
#   with .env but no .maestro/ in MAESTRO_PROJECT_ROOT.
# Real attribute is `app` (line 1619). Use a fake DEEPSEEK_API_KEY to bypass
# the credentials check — we're only verifying the module loads cleanly,
# not that it can dispatch.
V002_DIR=$(mktemp -d /tmp/epic2_smoke_v002.XXXXXX)
TMP_DIRS+=("$V002_DIR")
echo "MAESTRO_FAKE_VAR=1" > "$V002_DIR/.env"

OUTPUT12=$(DEEPSEEK_API_KEY=fake-key-for-smoke MAESTRO_PROJECT_ROOT="$V002_DIR" \
    python3 -c "
import maestro.mcp_server as m
assert hasattr(m, 'app'), 'maestro.mcp_server.app attribute missing'
print('OK')
" 2>&1) || true
echo "$OUTPUT12" | grep -q "^OK$" || fail "Check 12 bootstrap import failed (got: $OUTPUT12)"
pass "Check 12: bootstrap server module imports cleanly without .maestro/"

# ----------------------------------------------------------------------
# Check 13: server killed cleanly, port freed
PORT=$(echo "$URL" | grep -Eo '[0-9]+$')
kill "$LAUNCHER_PID" 2>/dev/null || true
wait "$LAUNCHER_PID" 2>/dev/null || true
LAUNCHER_PID=""
for i in {1..10}; do
    sleep 0.5
    if python3 -c "import socket; s=socket.socket(); s.bind(('127.0.0.1', $PORT)); s.close()" 2>/dev/null; then
        pass "Check 13: port $PORT freed after server kill"
        break
    fi
    [ "$i" -eq 10 ] && fail "port $PORT still occupied after 5s"
done

echo
echo "ALL AUTOMATED CHECKS PASSED"
