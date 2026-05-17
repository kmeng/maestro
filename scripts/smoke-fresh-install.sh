#!/usr/bin/env bash
set -euo pipefail

# Fresh-install smoke test for maestro release artifacts
# Usage: see scripts/smoke-fresh-install.README.md

# --- helpers ---
fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# --- setup ---
WORK="$(mktemp -d)"
trap "rm -rf '$WORK'" EXIT
echo "==> workspace $WORK"

# Determine artifact to use
if [[ -n "${MAESTRO_ARTIFACT_PATH:-}" ]]; then
    ARTIFACT="$MAESTRO_ARTIFACT_PATH"
    pass "using provided artifact $ARTIFACT"
else
    REPO="${MAESTRO_GITHUB_REPO:-kmeng/maestro}"
    echo "==> downloading latest release from $REPO"
    OS_TYPE="$(uname -s)"
    ARCH="$(uname -m)"

    if [[ "$OS_TYPE" != "Darwin" && "$OS_TYPE" != "Linux" ]]; then
        echo "smoke test does not yet support Windows; see PowerShell variant TBD"
        exit 0
    fi

    if [[ "$OS_TYPE" == "Darwin" ]]; then
        if [[ "$ARCH" != "arm64" ]]; then
            fail "only macOS arm64 artifact is available; you have $ARCH"
        fi
        ASSET_PATTERN="maestro-macos-arm64.tar.gz"
    else # Linux
        if [[ "$ARCH" != "x86_64" ]]; then
            fail "only Linux x86_64 artifact is available; you have $ARCH"
        fi
        ASSET_PATTERN="maestro-linux-x64.tar.gz"
    fi

    if ! command -v gh &>/dev/null; then
        fail "gh CLI not installed; install it (https://cli.github.com) to download the release artifact"
    fi

    if ! gh release download --pattern "$ASSET_PATTERN" --repo "$REPO" --dir "$WORK"; then
        fail "downloading $ASSET_PATTERN failed; check if a release exists in $REPO"
    fi
    ARTIFACT="$(echo "$WORK"/maestro-*.tar.gz)"
    if [[ ! -f "$ARTIFACT" ]]; then
        fail "downloaded artifact not found at $ARTIFACT"
    fi
    pass "acquired artifact $ARTIFACT"
fi

# --- extract ---
echo "==> extracting"
EXTRACT_DIR="$WORK/extracted"
mkdir -p "$EXTRACT_DIR"
tar -xzf "$ARTIFACT" -C "$EXTRACT_DIR"
pass "extracted to $EXTRACT_DIR"

# --- locate binary ---
BIN="$(find "$EXTRACT_DIR" -type f \( -name maestro -o -name maestro.exe \) -print -quit)"
if [[ -z "$BIN" ]]; then
    fail "maestro binary not found under $EXTRACT_DIR"
fi
chmod +x "$BIN"
pass "binary found: $BIN"

# --- version check ---
if [[ -n "${EXPECTED_VERSION:-}" ]]; then
    EXPECTED="$EXPECTED_VERSION"
else
    if [[ ! -f pyproject.toml ]]; then
        fail "EXPECTED_VERSION not set and pyproject.toml not found in cwd"
    fi
    EXPECTED="$(grep -E '^version\s*=\s*"[^"]+"' pyproject.toml | head -1 | sed 's/.*"\([^"]*\)".*/\1/')"
    if [[ -z "$EXPECTED" ]]; then
        fail "could not parse version from pyproject.toml"
    fi
fi
VERSION_OUT="$("$BIN" --version 2>&1 || true)"
if ! echo "$VERSION_OUT" | grep -qF "$EXPECTED"; then
    fail "--version output did not contain '$EXPECTED'; got: $VERSION_OUT"
fi
pass "--version contains $EXPECTED"

# --- install with isolated HOME ---
FAKE_HOME="$WORK/fake-home"
mkdir -p "$FAKE_HOME/.claude"
echo "==> running install --force with HOME=$FAKE_HOME"
if ! HOME="$FAKE_HOME" "$BIN" install --force; then
    fail "install --force failed"
fi

MCP_JSON="$FAKE_HOME/.claude/mcp.json"
if [[ ! -f "$MCP_JSON" ]]; then
    fail "mcp.json not created at $MCP_JSON"
fi
pass "install created mcp.json"

# --- validate mcp.json content ---
BIN_ABS="$(python3 -c "import os; print(os.path.realpath('$BIN'))" 2>/dev/null || realpath "$BIN" 2>/dev/null || readlink -f "$BIN" 2>/dev/null || echo "$BIN")"

if command -v jq &>/dev/null; then
    MCP_COMMAND="$(jq -r '.mcpServers.maestro.command' "$MCP_JSON")"
    MCP_ARGS="$(jq -r '.mcpServers.maestro.args | join("\n")' "$MCP_JSON")"
else
    # fallback to python
    MCP_COMMAND="$(python3 -c "import json; print(json.load(open('$MCP_JSON'))['mcpServers']['maestro']['command'])")"
    MCP_ARGS="$(python3 -c "import json; print('\n'.join(json.load(open('$MCP_JSON'))['mcpServers']['maestro']['args']))")"
fi

if [[ "$MCP_COMMAND" != "$BIN_ABS" ]]; then
    fail "mcp.json command '$MCP_COMMAND' != binary absolute path '$BIN_ABS'"
fi

if [[ "$MCP_ARGS" != "serve" ]]; then
    fail "mcp.json args should be ['serve'] but got: $MCP_ARGS"
fi
pass "mcp.json contains correct command and args"

# --- idempotency ---
cp "$MCP_JSON" "$WORK/mcp-before.json"
if ! HOME="$FAKE_HOME" "$BIN" install --force; then
    fail "second install --force failed"
fi
if ! cmp -s "$WORK/mcp-before.json" "$MCP_JSON"; then
    fail "mcp.json changed after second install; not idempotent"
fi
pass "install is idempotent (mcp.json unchanged)"

# --- MCP handshake ---
echo "==> MCP handshake"

# find a timeout command
TIMEOUT_CMD=""
if command -v timeout &>/dev/null; then
    TIMEOUT_CMD="timeout 10"
elif command -v gtimeout &>/dev/null; then
    TIMEOUT_CMD="gtimeout 10"
fi

if [[ -n "$TIMEOUT_CMD" ]]; then
    HANDSHAKE_OUT=$( ( cat <<'EOF'
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"smoke","version":"0.0.1"}}}
{"jsonrpc":"2.0","method":"notifications/initialized","params":{}}
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
EOF
      sleep 5
    ) | HOME="$FAKE_HOME" DEEPSEEK_API_KEY=fake-key-for-smoke $TIMEOUT_CMD "$BIN" serve 2>&1 || true )
else
    # Python fallback (requires Python3)
    if ! command -v python3 &>/dev/null; then
        fail "timeout/gtimeout not found and python3 not available; install coreutils or python3"
    fi
    HANDSHAKE_OUT="$(BIN="$BIN" FAKE_HOME="$FAKE_HOME" python3 <<'PYEOF'
import os, subprocess
stdin_data = b'''{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"smoke","version":"0.0.1"}}}
{"jsonrpc":"2.0","method":"notifications/initialized","params":{}}
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
'''
env = {**os.environ, "HOME": os.environ["FAKE_HOME"], "DEEPSEEK_API_KEY": "fake-key-for-smoke"}
proc = subprocess.Popen([os.environ["BIN"], "serve"],
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT, env=env)
try:
    out, _ = proc.communicate(input=stdin_data, timeout=10)
    print(out.decode(), end="")
except subprocess.TimeoutExpired:
    proc.kill()
    out, _ = proc.communicate()
    print(out.decode(), end="")
PYEOF
)"
fi

# Parse handshake output for tools/list response (look for id:2)
EXPECTED_TOOLS=("coder" "librarian" "reviewer" "scribe" "verifier" "spec_writer")
TOOL_NAMES_FILE="$WORK/tool_names.txt"

echo "$HANDSHAKE_OUT" | python3 -c "
import sys, json
found=False
for line in sys.stdin:
    line = line.strip()
    if not line: continue
    try:
        data = json.loads(line)
    except Exception:
        continue
    if data.get('id') == 2 and 'result' in data:
        tools = [t['name'] for t in data['result']['tools']]
        print('\n'.join(tools))
        found=True
        break
if not found:
    sys.exit(1)
" > "$TOOL_NAMES_FILE" || fail "handshake: did not find tools/list response; server output:
$HANDSHAKE_OUT"

TOOLS_FOUND="$(cat "$TOOL_NAMES_FILE")"
for tool in "${EXPECTED_TOOLS[@]}"; do
    if ! echo "$TOOLS_FOUND" | grep -qxF "$tool"; then
        fail "handshake: missing tool '$tool'. Got tools:
$TOOLS_FOUND"
    fi
done
pass "MCP handshake returned all 6 expected tools"

echo "ALL PASS"
