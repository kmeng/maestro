# Smoke Test: Fresh Install of Maestro Release Artifact

## When to run

- After a GitHub release is published (post-release verification)
- Before tagging a release, to smoke a locally built artifact
- Manually on pull requests that modify the install or MCP paths

## How to run

### Test against a local artifact

```bash
MAESTRO_ARTIFACT_PATH=./dist/maestro-macos-arm64.tar.gz bash scripts/smoke-fresh-install.sh
```

### Test against the latest GitHub release

```bash
bash scripts/smoke-fresh-install.sh
```

The script will download the appropriate asset for your OS (macOS arm64 or Linux x64) using the `gh` CLI. Set `GH_TOKEN` if running locally without interactive authentication.

## Environment variables

- `MAESTRO_ARTIFACT_PATH` — path to a local `.tar.gz` artifact (overrides download)
- `MAESTRO_GITHUB_REPO` — GitHub repository (default `kmeng/maestro`)
- `EXPECTED_VERSION` — version substring the binary's `--version` must include (defaults to parsed from `pyproject.toml`)

## What the smoke verifies

1. Artifact can be downloaded (or used from disk) and extracted.
2. The binary runs and reports the expected version.
3. `maestro install --force` writes `~/.claude/mcp.json` correctly when using an isolated `HOME`.
4. The install command is idempotent — `mcp.json` is byte-identical after a second run.
5. The MCP server starts, performs a `tools/list` handshake, and returns exactly the 6 expected tool names: `coder`, `librarian`, `reviewer`, `scribe`, `verifier`, `spec_writer`.

## Caveats

- **No real API calls**: the test uses a fake `DEEPSEEK_API_KEY` and never makes provider API requests.
- **Windows not supported**: a PowerShell variant is deferred. The bash script skips gracefully on non-Darwin/Linux systems.
- **Requires Python 3** for JSON parsing and as a fallback if `timeout` / `gtimeout` is unavailable.
