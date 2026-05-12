#!/usr/bin/env bash
# Epic 3 自动化验收脚本 (automated portion; manual portion in epic3.md)
#
# 覆盖：
# - AC1 dispatch.start / dispatch.end 事件可见
# - AC2 history 视图按时间倒序
# - AC3 live SSE 实时推送（连接前已存在 + 连接后写入；
#       覆盖 tests/test_dispatch_log_stream.py 两个 @pytest.mark.skip 测试）
# - AC4 失败事件进 problem panel
# - AC5 refused 事件进 problem panel + CTA 指向 /team
# - AC6 fallback 事件进 problem panel + 同 (role, fallback_model) 分组 + CTA 指向 /wizard
# - AC7 logs 目录不可写时 emit_event 不抛异常 + 走 stderr fallback
#
# AC8（MCP coder 接口未变）需 Claude Code + DEEPSEEK_API_KEY，留给手动清单。

set -euo pipefail
cd "$(dirname "$0")/../.."

declare -a TMP_DIRS=()
declare -a TMP_FILES=()
LAUNCHER_PID=""
LAUNCHER_DIR=""
URL=""

cleanup() {
    if [ -n "${LAUNCHER_PID:-}" ]; then kill "$LAUNCHER_PID" 2>/dev/null || true; fi
    # 自动化里 chmod 000 后必须恢复，否则 trap 自身的 rm -rf 会失败
    if [ -n "${LAUNCHER_DIR:-}" ] && [ -d "$LAUNCHER_DIR/.maestro/logs" ]; then
        chmod -R u+rwX "$LAUNCHER_DIR/.maestro" 2>/dev/null || true
    fi
    for d in "${TMP_DIRS[@]}"; do rm -rf "$d" 2>/dev/null || true; done
    for f in "${TMP_FILES[@]}"; do rm -f "$f" 2>/dev/null || true; done
}
trap cleanup EXIT INT TERM

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1" >&2; exit 1; }

# 注入一个真实 T3.1 schema 的事件到 launcher cwd 的 dispatch.jsonl
# 用法：emit_event <kind> <key=value>...
# kind 取值：start | end | failed | refused | fallback
emit_event() {
    local project="$1"; shift
    local kind="$1"; shift
    PYTHONPATH="$(pwd)" python3 - "$project" "$kind" "$@" <<'PYEOF'
import os, sys
from datetime import datetime, timezone
from pathlib import Path

project = Path(sys.argv[1])
kind = sys.argv[2]
fields = dict(arg.split("=", 1) for arg in sys.argv[3:])

# Workdir matters: emit_event uses project_root arg, not cwd.
from maestro.dispatch_log.events import (
    DispatchStartEvent, DispatchEndEvent, DispatchFailedEvent,
    DispatchFallbackConfigAbsentEvent, DispatchRefusedConfigInvalidEvent,
)
from maestro.dispatch_log.writer import emit_event

# 时间戳允许偏移：用 ts_offset_sec 模拟时间倒序
ts_offset = float(fields.pop("ts_offset_sec", "0"))
ts = datetime.now(timezone.utc).fromtimestamp(
    datetime.now(timezone.utc).timestamp() + ts_offset, tz=timezone.utc
)

common = dict(request_id=fields.pop("request_id"), timestamp=ts)
if kind == "start":
    ev = DispatchStartEvent(
        **common,
        role=fields.pop("role", "coder"),
        model=fields.pop("model", "deepseek-v4-pro"),
        member=fields.pop("member", "alice"),
        input_summary=fields.pop("input_summary", "smoke input"),
    )
elif kind == "end":
    ev = DispatchEndEvent(
        **common,
        output_summary=fields.pop("output_summary", "smoke output"),
        duration_ms=int(fields.pop("duration_ms", "1500")),
    )
elif kind == "failed":
    ev = DispatchFailedEvent(
        **common,
        duration_ms=int(fields.pop("duration_ms", "200")),
        error_kind=fields.pop("error_kind", "RuntimeError"),
        error_message=fields.pop("error_message", "smoke failure"),
    )
elif kind == "refused":
    ev = DispatchRefusedConfigInvalidEvent(
        **common,
        validation_error_field=fields.pop("validation_error_field", "roles.coder"),
        validation_error_message=fields.pop("validation_error_message", "smoke refused"),
    )
elif kind == "fallback":
    ev = DispatchFallbackConfigAbsentEvent(
        **common,
        role=fields.pop("role", "coder"),
        fallback_model=fields.pop("fallback_model", "deepseek-v4-pro"),
    )
else:
    raise SystemExit(f"unknown event kind: {kind}")

if fields:
    raise SystemExit(f"unconsumed fields: {fields}")

emit_event(ev, project)
PYEOF
}

# ----------------------------------------------------------------------
# Check 1: pip install -e . 当前
pip install -e . >/dev/null 2>&1 || fail "pip install -e . failed"
pass "Check 1: pip install -e . succeeded"

# ----------------------------------------------------------------------
# Check 2: launcher 在 tmp 目录起来
LAUNCHER_DIR=$(mktemp -d /tmp/epic3_smoke_launcher.XXXXXX)
TMP_DIRS+=("$LAUNCHER_DIR")
LOG_FILE=$(mktemp /tmp/epic3_smoke_launcher_log.XXXXXX)
TMP_FILES+=("$LOG_FILE")

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
# Check 3: AC1 + AC2 — 注入 start+end，倒序 history
# 注意：history 按 timestamp 倒序，最新在上。用 ts_offset_sec 拉开 3 个时间戳。
emit_event "$LAUNCHER_DIR" start  request_id=req-old   ts_offset_sec=-30  input_summary="oldest call"
emit_event "$LAUNCHER_DIR" end    request_id=req-old   ts_offset_sec=-29  output_summary="ok-old"  duration_ms=1500
emit_event "$LAUNCHER_DIR" start  request_id=req-mid   ts_offset_sec=-15  input_summary="middle call"
emit_event "$LAUNCHER_DIR" end    request_id=req-mid   ts_offset_sec=-14  output_summary="ok-mid"  duration_ms=2500
emit_event "$LAUNCHER_DIR" start  request_id=req-new   ts_offset_sec=-1   input_summary="newest call"
emit_event "$LAUNCHER_DIR" end    request_id=req-new   ts_offset_sec=0    output_summary="ok-new"  duration_ms=800

HISTORY_HTML=$(curl -fsS "$URL/history")
echo "$HISTORY_HTML" | grep -q "Maestro · 调度历史" || fail "history title 不符合 'Maestro · 调度历史' 约定"
echo "$HISTORY_HTML" | grep -q "ok-new" || fail "history 缺 newest 输出"
echo "$HISTORY_HTML" | grep -q "ok-mid" || fail "history 缺 middle 输出"
echo "$HISTORY_HTML" | grep -q "ok-old" || fail "history 缺 oldest 输出"
echo "$HISTORY_HTML" | grep -q "✓" || fail "history 缺 ✓ 成功图标"
echo "$HISTORY_HTML" | grep -q "成功" || fail "history 缺中文 '成功' 标签"

# 倒序断言：req-new 在 req-mid 之前出现，req-mid 在 req-old 之前出现
POS_NEW=$(echo "$HISTORY_HTML" | grep -bo "ok-new" | head -1 | cut -d: -f1)
POS_MID=$(echo "$HISTORY_HTML" | grep -bo "ok-mid" | head -1 | cut -d: -f1)
POS_OLD=$(echo "$HISTORY_HTML" | grep -bo "ok-old" | head -1 | cut -d: -f1)
[ -n "$POS_NEW" ] && [ -n "$POS_MID" ] && [ -n "$POS_OLD" ] || fail "history 顺序断言取不到位置"
[ "$POS_NEW" -lt "$POS_MID" ] || fail "history 顺序错：req-new 应在 req-mid 之前 ($POS_NEW vs $POS_MID)"
[ "$POS_MID" -lt "$POS_OLD" ] || fail "history 顺序错：req-mid 应在 req-old 之前 ($POS_MID vs $POS_OLD)"
pass "Check 3: AC1+AC2 history 含 start/end 且按时间倒序"

# ----------------------------------------------------------------------
# Check 4: AC4 — failed 进 problem panel
emit_event "$LAUNCHER_DIR" start  request_id=req-fail  ts_offset_sec=-5  input_summary="failing call"
emit_event "$LAUNCHER_DIR" failed request_id=req-fail  ts_offset_sec=-4  error_kind=ValueError  error_message="boom"

PROBLEMS_HTML=$(curl -fsS "$URL/problems")
echo "$PROBLEMS_HTML" | grep -q "Maestro · 问题面板" || fail "problem panel title 不符合 'Maestro · 问题面板' 约定"
echo "$PROBLEMS_HTML" | grep -q "失败的调度" || fail "problem panel 缺 '失败的调度' 分区"
echo "$PROBLEMS_HTML" | grep -q "boom" || fail "problem panel 缺 failed 事件 error_message"
pass "Check 4: AC4 failed 进 problem panel"

# ----------------------------------------------------------------------
# Check 5: AC5 — refused 进 problem panel，CTA 指向 /team
emit_event "$LAUNCHER_DIR" refused request_id=req-refused  ts_offset_sec=-3 \
    validation_error_field=roles.coder  validation_error_message="model 字段缺失"

PROBLEMS_HTML=$(curl -fsS "$URL/problems")
echo "$PROBLEMS_HTML" | grep -q "团队配置被拒" || fail "problem panel 缺 '团队配置被拒' 分区"
echo "$PROBLEMS_HTML" | grep -q 'href="/team"' || fail "problem panel refused 行 CTA 未指向 /team"
echo "$PROBLEMS_HTML" | grep -q "model 字段缺失" || fail "problem panel 缺 refused validation_error_message"
pass "Check 5: AC5 refused 进 problem panel + CTA → /team"

# ----------------------------------------------------------------------
# Check 6: AC6 — fallback 进 problem panel，同 (role, fallback_model) 分组，CTA → /wizard
# 注入 3 条同组 + 1 条不同组，问题面板应折叠为 2 个分组
emit_event "$LAUNCHER_DIR" fallback request_id=req-fb-a1  ts_offset_sec=-9  role=coder       fallback_model=deepseek-v4-pro
emit_event "$LAUNCHER_DIR" fallback request_id=req-fb-a2  ts_offset_sec=-8  role=coder       fallback_model=deepseek-v4-pro
emit_event "$LAUNCHER_DIR" fallback request_id=req-fb-a3  ts_offset_sec=-7  role=coder       fallback_model=deepseek-v4-pro
emit_event "$LAUNCHER_DIR" fallback request_id=req-fb-b1  ts_offset_sec=-6  role=librarian   fallback_model=qwen-flash

PROBLEMS_HTML=$(curl -fsS "$URL/problems")
echo "$PROBLEMS_HTML" | grep -q "团队配置缺失" || fail "problem panel 缺 '团队配置缺失（降级）' 分区"
echo "$PROBLEMS_HTML" | grep -q 'href="/wizard"' || fail "problem panel fallback 行 CTA 未指向 /wizard"
# 同组 3 条应折成一行带计数；不同组各一行
# 用 grep -c 数 fallback_model=deepseek-v4-pro 在 HTML 中作为分组键的出现次数（应 == 1，不是 3）
COUNT_DEEPSEEK=$(echo "$PROBLEMS_HTML" | grep -c "deepseek-v4-pro" || true)
COUNT_QWEN=$(echo "$PROBLEMS_HTML" | grep -c "qwen-flash" || true)
[ "$COUNT_DEEPSEEK" -ge 1 ] || fail "fallback 分组缺 deepseek-v4-pro 标识"
[ "$COUNT_QWEN" -ge 1 ] || fail "fallback 分组缺 qwen-flash 标识"
# 计数表示分组生效（如 "× 3" 或 "3 次" 类提示）：要么 HTML 中能看到 "3"，要么模板未呈现计数；
# 至少不应该是 deepseek-v4-pro 重复出现 3 次（每条独立一行）
[ "$COUNT_DEEPSEEK" -lt 3 ] || fail "fallback 未分组：deepseek-v4-pro 出现 $COUNT_DEEPSEEK 次（>=3 表示未折叠）"
pass "Check 6: AC6 fallback 进 problem panel + 分组 + CTA → /wizard"

# ----------------------------------------------------------------------
# Check 7: AC7 — logs 目录不可写时 emit_event 不抛异常
LOGS_DIR="$LAUNCHER_DIR/.maestro/logs"
[ -d "$LOGS_DIR" ] || fail "logs 目录不存在，前面的 emit 没生效？"

# 把 logs 目录设为不可写，再尝试 emit；预期 stderr 有 "dispatch log ... failed" 但脚本不挂
chmod 000 "$LOGS_DIR"
SET=$(PYTHONPATH="$(pwd)" python3 - "$LAUNCHER_DIR" 2>&1 <<'PYEOF'
import sys
from datetime import datetime, timezone
from pathlib import Path

project = Path(sys.argv[1])
from maestro.dispatch_log.events import DispatchStartEvent
from maestro.dispatch_log.writer import emit_event

ev = DispatchStartEvent(
    request_id="req-readonly",
    timestamp=datetime.now(timezone.utc),
    role="coder", model="m", member="x", input_summary="readonly probe",
)
emit_event(ev, project)  # 必须不抛
print("EMIT_RETURNED_OK")
PYEOF
)
chmod -R u+rwX "$LOGS_DIR" 2>/dev/null || true

echo "$SET" | grep -q "EMIT_RETURNED_OK" || fail "AC7: emit_event 未正常返回（logs 只读时应静默 fallback）"
echo "$SET" | grep -q "dispatch log" || fail "AC7: 未在 stderr 看到 'dispatch log ... failed' 诊断"
pass "Check 7: AC7 logs 不可写时 emit_event 不抛异常 + 走 stderr fallback"

# ----------------------------------------------------------------------
# Check 8: AC3 — SSE endpoint 实时推送（覆盖两个 @pytest.mark.skip）
# 子检查 8a：连接前已存在的事件应被 deliver
SSE_OUT=$(mktemp /tmp/epic3_smoke_sse_a.XXXXXX)
TMP_FILES+=("$SSE_OUT")

emit_event "$LAUNCHER_DIR" start request_id=req-sse-pre ts_offset_sec=0 input_summary="pre-connect event"

curl -fsS --no-buffer -N "$URL/api/dispatch_log/stream" > "$SSE_OUT" 2>/dev/null &
SSE_PID=$!
sleep 1.5  # 让 SSE 把已有事件 flush 出来
kill "$SSE_PID" 2>/dev/null || true
wait "$SSE_PID" 2>/dev/null || true

grep -q "req-sse-pre" "$SSE_OUT" || fail "AC3 子检查 8a：SSE 未投递连接前已有的 req-sse-pre 事件 (output: $(cat "$SSE_OUT" | head -c 500))"
pass "Check 8a: SSE 投递连接前已存在事件 (覆盖 test_stream_yields_pre_existing_events)"

# 子检查 8b：连接后新写入的事件应被 deliver
SSE_OUT2=$(mktemp /tmp/epic3_smoke_sse_b.XXXXXX)
TMP_FILES+=("$SSE_OUT2")

curl -fsS --no-buffer -N "$URL/api/dispatch_log/stream" > "$SSE_OUT2" 2>/dev/null &
SSE_PID=$!
sleep 0.8  # 让连接建立 + flush 已有事件
emit_event "$LAUNCHER_DIR" start request_id=req-sse-post ts_offset_sec=0 input_summary="post-connect event"
sleep 2.0  # tail_log 默认 poll_interval=1.0，留两个 poll 的余量
kill "$SSE_PID" 2>/dev/null || true
wait "$SSE_PID" 2>/dev/null || true

grep -q "req-sse-post" "$SSE_OUT2" || fail "AC3 子检查 8b：SSE 未投递连接后写入的 req-sse-post 事件 (output tail: $(tail -c 500 "$SSE_OUT2"))"
pass "Check 8b: SSE 投递连接后新事件 (覆盖 test_stream_yields_new_events_after_connect)"

# ----------------------------------------------------------------------
echo ""
echo "ALL CHECKS PASSED — Epic 3 自动化烟测通过 (AC1/AC2/AC3/AC4/AC5/AC6/AC7)"
echo "AC8 (MCP coder 接口未变) 见 tests/smoke/epic3.md § 6 手动确认"
