# Design: server self-loads config from .env

**Issue**: #6
**Status**: draft

## Problem

After v0.0.1, every MCP client (Claude Code via `~/.claude.json`, Claude Desktop via `claude_desktop_config.json`) requires the user to embed `DEEPSEEK_API_KEY` into the client's own JSON config file. This violates the spirit of architecture P3 (secrets stay in env vars, not config files), is duplicated per-client, and surfaces the key in plaintext on disk in non-obvious places.

The server should be the only thing that reads the key. Clients should only know `command + args`.

## Out of scope

- Multiple environments (dev / prod / staging). Single `.env` only.
- Encryption at rest, vault integration, or any secret-management layer.
- Adding new provider keys (Qwen, OpenAI, etc.). Only `DEEPSEEK_API_KEY` and existing `MAESTRO_*` knobs.
- Hot-reload of `.env` during a running session.
- Changes to the `cheap_code_gen` tool signature.
- Migration of `MAESTRO_LOG_DIR` / `MAESTRO_DEEPSEEK_MODEL` / `MAESTRO_TIMEOUT_SEC` from `os.environ` to documented `.env` keys (deferred — see OPEN-1).

## Functional design

### Happy path the user sees

1. Clone repo, create venv, install requirements
2. `cp .env.example .env`, open `.env`, paste `DEEPSEEK_API_KEY=sk-...`
3. Register server in client of choice with command + args only — no `env` block in JSON, no `--env` flag
4. Restart client, `/mcp` shows maestro connected, test dispatch returns

### Failure paths the user sees

Each error tells the user the exact next action, not a generic "missing" message:

- **`.env` does not exist AND no shell export of `DEEPSEEK_API_KEY`**:
  ```
  ERROR: DEEPSEEK_API_KEY not set.
    Copy <project_root>/.env.example to <project_root>/.env and add your key.
  ```
- **`.env` exists but `DEEPSEEK_API_KEY` is missing or empty in it**:
  ```
  ERROR: DEEPSEEK_API_KEY not set in <project_root>/.env.
    Add a line: DEEPSEEK_API_KEY=your-key-here
  ```

### Single source of truth

When `.env` is present, it is the authoritative source: values in `.env` **override** anything already in `os.environ`. This makes the documented setup path unambiguous — what's in `.env` is what runs. A stale `export DEEPSEEK_API_KEY=...` in the user's shell never silently shadows the `.env` value.

If `.env` is absent and `DEEPSEEK_API_KEY` happens to be in the shell environment (e.g. CI), the existing v0.0.1 export path still works. This is undocumented fallback, not a promoted second path.

## Technical design

### File: `.env.example` at repo root (new, committed)

```
# Maestro configuration — copy this file to .env and fill in your values.
# .env is gitignored; your real keys never leave your machine.

DEEPSEEK_API_KEY=
```

Single documented variable. Other knobs stay undocumented in `.env.example` (see OPEN-1).

### File: `.env` at repo root (gitignored, user-created)

`.env` is already excluded by the `.gitignore` rule `.env`. No `.gitignore` change needed.

Path choice: **repo root**, not `bootstrap/`. Rationale: future config will span more than `bootstrap/` (workers, providers, runtime config). Putting `.env` at root anticipates that without committing to `bootstrap/` as the permanent config home.

### Loader function

Added to `bootstrap/maestro_server.py`, called before `DEEPSEEK_API_KEY` is read:

```python
def _load_dotenv(path: Path) -> None:
    """Read KEY=VALUE lines from path into os.environ.

    - Values in the file overwrite any existing os.environ entry, making
      .env the single authoritative source when present.
    - Lines starting with # or without '=' are ignored.
    - Surrounding single/double quotes on the value are stripped.
    - Silently no-op if path does not exist.
    """
    if not path.is_file():
        return
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip()
            if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
                val = val[1:-1]
            os.environ[key] = val


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_load_dotenv(_PROJECT_ROOT / ".env")
```

Properties honored:
- **P7 (minimal deps)**: stdlib only, no new dependency.
- **P3 (security by default)**: never logs or echoes loaded values.
- **P5 (fail loud, recover gracefully)**: no exceptions raised on malformed lines; the existing key check immediately downstream produces the actionable error.
- **P1 (simplicity)**: ~15 lines, no abstractions. Single source of truth (`.env` when present) avoids "which one wins?" confusion for users.

### Actionable error replacement

Replace the current bare check:

```python
if not DEEPSEEK_API_KEY:
    print("ERROR: DEEPSEEK_API_KEY environment variable not set", file=sys.stderr)
    sys.exit(1)
```

with:

```python
if not DEEPSEEK_API_KEY:
    env_path = _PROJECT_ROOT / ".env"
    if not env_path.is_file():
        print(
            f"ERROR: DEEPSEEK_API_KEY not set.\n"
            f"  Copy {_PROJECT_ROOT}/.env.example to {env_path} and add your key.",
            file=sys.stderr,
        )
    else:
        print(
            f"ERROR: DEEPSEEK_API_KEY not set in {env_path}.\n"
            f"  Add a line: DEEPSEEK_API_KEY=your-key-here",
            file=sys.stderr,
        )
    sys.exit(1)
```

### What does NOT change

- `cheap_code_gen` tool: signature, schema, prompt, behavior — all unchanged
- `MAESTRO_LOG_DIR` / `MAESTRO_DEEPSEEK_MODEL` / `MAESTRO_TIMEOUT_SEC`: still `os.environ`-only (the loader will pick them up if user puts them in `.env`, but `.env.example` does not advertise this — undocumented capability for v0.0.2)
- `requirements.txt`: unchanged
- `.gitignore`: unchanged

## Branch & merge flow (model B — release branch)

This issue lives inside the v0.0.2 release window. Three tiers of branches:

```
main                          (release, on remote, only updated via PR from v0.0.2)
 └── v0.0.2                   (release integration, on remote, target of feature PRs)
      └── feature/6-env-loading   (this issue, on remote, target of v0.0.2 release PR)
           ├── feature/6-env-loading-task1   (local only, merged into feature branch + deleted)
           └── feature/6-env-loading-task2   (local only, merged into feature branch + deleted)
```

Rules:
- **`v0.0.2`**: created from `main` at start of v0.0.2 work. Lives on `origin`. Receives feature PRs.
- **`feature/6-env-loading`**: created from `v0.0.2`. Pushed to `origin` once both tasks are integrated locally. PR target: `v0.0.2` (NOT `main`).
- **Task sub-branches** (`-task1`, `-task2`): local only, never pushed. Merged into `feature/6-env-loading` locally with `--no-ff` (preserves task boundaries in feature branch history), then deleted locally.
- **Release**: when v0.0.2 is complete (this issue + any other v0.0.2 issues), open a PR `v0.0.2 → main`. Squash-merge per governance.md.

This honors:
- v0.0.1 branch policy: temporary task branches stay local
- governance.md "one PR = one closed loop": feature PR closes issue #6, release PR closes the v0.0.2 milestone
- H2 "no direct push to main": main only updated via release PR

## Task breakdown

Two tasks, both inside `feature/6-env-loading`. Each merge into the feature branch keeps the feature branch runnable.

### Task 1 — load .env at server startup

Local branch: `feature/6-env-loading-task1` (off `feature/6-env-loading`)

Files changed:
- `bootstrap/maestro_server.py`: add `_load_dotenv`, call it at module load, replace bare error with actionable variants
- `.env.example`: new file at repo root

Local commit message: `feat(#6): load .env at server startup`

Runnable after this merge into `feature/6-env-loading` in three modes:
- `.env` present and filled → works (new path)
- shell `export DEEPSEEK_API_KEY=...` only → works (undocumented fallback)
- neither → exits with the path-pointing actionable error

QUICKSTART is intentionally not changed in Task 1; the v0.0.1 export-based instructions still describe a working (now-undocumented) path.

### Task 2 — teach .env flow and add Claude Desktop guide

Local branch: `feature/6-env-loading-task2` (off `feature/6-env-loading`, after Task 1 merged in)

Files changed:
- `bootstrap/QUICKSTART.md`: rewrite Step 2 (`cp .env.example .env`), simplify Step 4 (no `--env`), add Step 4b for Claude Desktop with a `claude_desktop_config.json` snippet

Local commit message: `docs(#6): teach .env flow and add Claude Desktop guide`

Runnable after this merge: server behavior already supports `.env` from Task 1; Task 2 only teaches users the new path.

### After both tasks merged into `feature/6-env-loading`

- Append v0.0.2 section to `BUILD_LOG.md` summarizing this feature's AI authorship — single commit on the feature branch
- Push `feature/6-env-loading` to origin
- Open PR: `feature/6-env-loading` → `v0.0.2`

## Acceptance criteria

After both Task 1 and Task 2 are merged, a first-time user can:

- [ ] Fresh clone → venv + `pip install -r bootstrap/requirements.txt`
- [ ] `cp .env.example .env` and fill in their key
- [ ] Register the server in **either** Claude Code or Claude Desktop using only `command + args` (no env block / no `--env`)
- [ ] Restart the client; `/mcp` shows maestro connected
- [ ] Test dispatch round-trips successfully
- [ ] `git status` is clean (no `.env` shows up)
- [ ] `~/.claude.json` and `claude_desktop_config.json` contain no `sk-` strings
- [ ] When `.env` is absent, an existing `export DEEPSEEK_API_KEY=...` shell environment still works (undocumented fallback for CI / advanced setups)
- [ ] When both `.env` and shell `export` are set, `.env` wins (verified by setting export to a known-bad value, putting good value in `.env`, confirming server uses good value)
- [ ] Running with neither `.env` nor shell export produces the actionable, path-pointing error (verified by running with `env -i HOME=$HOME PATH=$PATH .venv/bin/python bootstrap/maestro_server.py`)

## Open questions / future watchpoints

Not blocking this design. Recorded so they don't get lost.

- **OPEN-1** (per maintainer guidance, minimal-change principle): `MAESTRO_LOG_DIR` / `MAESTRO_DEEPSEEK_MODEL` / `MAESTRO_TIMEOUT_SEC` are deliberately NOT documented in `.env.example` for v0.0.2. If users start needing per-project overrides, revisit — smallest fix is adding them to `.env.example` with the current defaults as comments. Watchpoint: if `.env.example` becomes a stale reference relative to actual config surface, users will be surprised.
- **OPEN-2**: The loader is intentionally minimal. It does NOT support multiline values, `export` prefix, or shell-style variable expansion (`KEY=$OTHER`). If a real user request needs any of these, evaluate `python-dotenv` vs growing the loader. Until then, minimal stays minimal.
- **OPEN-3**: No ADR is written for this decision. The choices (zero-dep loader, `.env` at repo root, `.env`-overrides semantics) are captured here and small enough that the design doc IS the rationale. If we later swap to python-dotenv or change loader semantics, an ADR documenting both forks would be appropriate then.
- **OPEN-4**: Future worker / provider configuration shape is undecided. `.env` is currently chosen at repo root anticipating that workers, provider adapters, and runtime knobs will eventually share the same config surface. If the project later evolves toward per-component config files (e.g. `bootstrap/.env`, `workers/<name>/config.yaml`), revisit whether `.env` at root is still the right home. Recording now so the decision can be reconsidered with a concrete trigger rather than rediscovered the hard way.
- **OPEN-5**: `docs/governance.md` does not yet describe the three-tier branch model (release → feature → task) used here. It currently lists `feature/<n>-<slug>`, `bootstrap/<version>` etc. as flat options, with no notion of a release-integration branch like `v0.0.2`. After this issue ships, `governance.md` should be updated in a dedicated issue to document the actual workflow we're using. Until then, this design doc is the authoritative reference for v0.0.2-era branch flow.
