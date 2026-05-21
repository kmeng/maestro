# Building the Maestro native binary (PyInstaller)

This doc covers how to build the single-file `maestro` executable from
the repo on macOS or Linux.  The build uses PyInstaller with the spec
file `pyinstaller.spec` at the repo root.

## Quick build

```bash
# at the repo root
bash scripts/build-binary.sh
```

The script creates a clean Python venv (`.venv-build`), installs all
runtime deps, runs PyInstaller, and verifies the resulting binary
(`dist/maestro`).  It prints a `PASS` or `FAIL` summary.

## What the build script does

1. **Clean** – removes `build/`, `dist/`, and `.venv-build/` to ensure
   a truly clean state.
2. **Venv** – creates a fresh venv, activates it, and installs:
   - the project itself (`pip install -e .`)
   - PyInstaller
   - extra runtime deps from `bootstrap/requirements.txt` (mcp,
     openai, python-dotenv) because they aren't yet in
     `pyproject.toml` dependencies (technical debt – see below).
3. **Build** – runs `pyinstaller pyinstaller.spec --noconfirm`.
4. **Smoke test** – runs `dist/maestro --version` (expected:
   `maestro 0.0.4`) and `dist/maestro install --dry-run` (must not
   write any file).

## Expected output

- `dist/maestro` – a single-file console executable.
- Size: 30–80 MB, depending on OS and architecture.

## Why `mcp`, `openai`, `python-dotenv` from `bootstrap/requirements.txt`

These packages are runtime dependencies but are not yet listed in
`pyproject.toml`.  The build script installs them explicitly.  A
follow-up task will move those deps into `pyproject.toml`.

## Troubleshooting

### `ModuleNotFoundError` at runtime

If you run `dist/maestro serve` or `dist/maestro webui` and get an
import error, a module is missing from the bundle.  PyInstaller's
static analysis can't trace all dynamic imports (uvicorn loops,
pydantic plugins, MCP protocol registry, etc.).  Add the missing
module name to the `hiddenimports` list in `pyinstaller.spec`, then
rebuild.

### Missing templates / static assets

The spec file explicitly adds `maestro/webui/templates`,
`maestro/webui/static`, and `maestro/scaffold/templates` as data
files.  If an HTML or CSS file is missing from the bundle, verify the
`datas` list in the spec.

### Binary is too large / too slow

We intentionally set `strip=False` and `upx=False` to avoid
code-signing issues and improve debuggability.  This is a deliberate
choice and will be revisited for release builds.

### macOS: "developer cannot be verified"

The binary is unsigned.  Right-click → Open, then confirm in the
dialogue.  Code signing and notarisation is planned for a later epic.

### Cross-architecture builds (Apple Silicon vs Intel)

PyInstaller produces a binary for the architecture of the machine it
runs on.  To support both, you must build on both an Intel Mac and an
Apple Silicon Mac (or use a CI matrix – see T10.3).  There is no
universal2 build in this task.

## Extending the spec for new dependencies

Add any new runtime dependencies to `pyproject.toml` (or
`bootstrap/requirements.txt` for now).  If the dependency uses dynamic
imports, also add it to `hiddenimports` in `pyinstaller.spec`.

## Manual full verification

The build-time smoke does **not** check the MCP or web servers.  You should
manually run:

```bash
dist/maestro serve        # MCP stdio server (handshake)
dist/maestro webui        # web UI (terminate after startup)
```

Both commands must start without `ModuleNotFoundError` or missing
template errors.

## Fresh-install smoke test

`scripts/smoke-fresh-install.sh` exercises the full download → extract →
`maestro install` → MCP `tools/list` handshake path against a release
artifact (idempotent; isolated `HOME`; no real provider calls). Run it
after a build or release:

```bash
MAESTRO_ARTIFACT_PATH=./dist/maestro-macos-arm64.tar.gz bash scripts/smoke-fresh-install.sh
```

Options, env vars, and the full check list:
[`scripts/smoke-fresh-install.README.md`](../../scripts/smoke-fresh-install.README.md).
