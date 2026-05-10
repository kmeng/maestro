# Design: T6.8 — retire begin_task.sh; dispatch attribution via parameters

**Issue**: #64
**Parent epic**: #56 (Epic 6 — effectiveness page)
**Related ADR**: ADR-0011 (dispatch-attribution-via-parameters)
**Supersedes**: design 56 §3.2 (env-var attribution)

## Problem

`bootstrap/maestro_server.py:201-207` reads `MAESTRO_CURRENT_TASK` and
`MAESTRO_CURRENT_ISSUE` env vars to attribute dispatch rows to a task.
The companion helper `scripts/begin_task.sh` requires the user to source
a shell script *before launching Claude Code* (so the MCP server inherits
the env). For shipped users this is unacceptable friction; even for
maestro-the-project's own dogfooding it is clumsy (a forgotten `source`
makes every dispatch unattributed and the bug is silent).

Decided 2026-05-10 (D7 superseded; D10 added to #56's body): replace
env-var attribution with explicit dispatch parameters, with git-branch
inference as a fallback. `begin_task.sh` deprecated, removed in v0.0.4.

## Functional view

What the orchestrator (Claude Code main session) experiences:

```
# Today (env-var path; about to be deprecated)
$ source scripts/begin_task.sh T6.8 64        # before launching CC
$ # … later, from a worker call
mcp__maestro__librarian({query: "..."})
# Server reads env, attributes to T6.8 / #64

# After T6.8 (parameter path; recommended)
mcp__maestro__librarian({query: "...", task_id: "T6.8", issue_number: 64})
# Server reads params directly, attributes to T6.8 / #64.
# No shell setup; works from any process invoking the MCP tool.
```

For users running ad-hoc dispatches without an issue concept, omitting
both params still works — the row is attributed via git branch (e.g.,
`feature/64-retire-begin-task` → `issue_number=64`) or marked
unattributed if the branch doesn't match the project's convention.

For `scribe` specifically, the existing required `issue_number` field
(used to format commit messages) is reused as the attribution issue —
no second parameter, no field collision. (Note: scribe's required
`issue_number / issue_title / issue_body` themselves are workflow-
coupled; tracked as a separate concern in
`project_pure_worker_schemas.md` memory, out of scope here.)

## Technical view

### Attribution chain (precedence)

In `_emit_dispatch_row`, attribution is resolved by trying these in
order and stopping at the first non-None:

1. **Explicit parameter** — `task_id` / `issue_number` passed as
   keyword args from the worker `_*_impl` function.
2. **Env var (deprecated)** — `MAESTRO_CURRENT_TASK` /
   `MAESTRO_CURRENT_ISSUE`. On first use per process, `warnings.warn`
   emits a `DeprecationWarning` (one-shot via module-level flag).
3. **Git branch inference** — `_infer_issue_from_branch()` parses the
   current branch name. Only `issue_number` (not `task_id`) can be
   inferred, since branch slugs don't reliably encode task IDs.
4. **Unattributed** — both stay `None`; row records as `noattr` in
   `row_id`, surfaces in the renderer's "unattributed" footnote.

Pseudo-code:

```python
def _resolve_attribution(task_id, issue_number):
    # Layer 1: explicit param
    if task_id or issue_number is not None:
        return task_id or None, issue_number  # explicit wins (allow partial)

    # Layer 2: env var (deprecated)
    env_task = os.environ.get("MAESTRO_CURRENT_TASK") or None
    env_issue = _parse_int_env("MAESTRO_CURRENT_ISSUE")
    if env_task or env_issue is not None:
        _warn_env_deprecation_once()
        return env_task, env_issue

    # Layer 3: git branch inference
    branch_issue = _infer_issue_from_branch()
    if branch_issue is not None:
        return None, branch_issue  # branch can't infer task_id

    # Layer 4: unattributed
    return None, None
```

Note: explicit-param case allows partial — e.g., orchestrator passes
`task_id` but not `issue_number`. The other-half is *not* backfilled
from env or branch; explicit-but-incomplete is treated as the user's
intent. This avoids subtle "I passed task_id and somehow got an issue
attached from my old env" surprise.

### Git branch inference

```python
_BRANCH_RE = re.compile(r"^(?:feature|fix|refactor|docs)/(\d+)-")

def _infer_issue_from_branch() -> Optional[int]:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=_repo_root(),  # cwd of the maestro_server module
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode != 0:
            return None
        m = _BRANCH_RE.match(result.stdout.strip())
        return int(m.group(1)) if m else None
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return None
```

Fail-soft: any error (no git, no branch, regex miss, parse failure) →
`None`, no exception propagated. Recompute per emit — branch can change
within a session.

### Schema changes (4 worker tools)

| Tool | New optional `task_id` | New optional `issue_number` | Notes |
|------|------------------------|------------------------------|-------|
| coder | + | + | Both new; both optional |
| librarian | + | + | Both new; both optional |
| reviewer | + | + | Both new; both optional |
| scribe | + | (already required) | Reuses existing `issue_number`; only `task_id` is new |

Worker `_*_impl` functions extract the new args via
`arguments.get("task_id")` / `arguments.get("issue_number")` and pass
them to `_emit_dispatch_row(task_id=..., issue_number=...)`.

For coder/librarian/reviewer: schema property type for `issue_number`
is `"integer"`, and validation at impl-call rejects non-int (mirroring
scribe's existing pattern at `bootstrap/maestro_server.py:1254`).

### Deprecation surfacing

Two warning surfaces, both fire at most once per process:

1. **`scripts/begin_task.sh`** — adds a `>&2` echo on every invocation:
   ```
   [deprecated] MAESTRO_CURRENT_TASK / MAESTRO_CURRENT_ISSUE will be
   removed in v0.0.4. Pass task_id / issue_number as parameters on
   each worker dispatch instead.
   ```
   Always fires (no per-process flag in shell).

2. **Server side** — when env-var values are *actually used* for
   attribution (i.e., layer 2 fires, not layer 1), `warnings.warn` once
   per process via a module-level boolean. Suppresses repeat noise on
   long sessions.

### CLAUDE.md update

Implementation-start protocol step amendment: when dispatching workers
for an issue, pass `task_id` (e.g., "T6.8") and `issue_number` (e.g.,
64) as parameters. Removes mention of `begin_task.sh`. The git-branch
fallback is documented as a safety net, not the primary path.

### Design 56 §3.2 update

Section rewrites the (a)/(b)/Decision triple. New body documents the
precedence chain + branch-inference helper + deprecation timeline.
Original D7 marked as superseded inline (already done in #56's body).

## Failure modes

- **Subprocess unavailable (no `git` binary)**: branch inference
  returns None; row goes to layer 4 (unattributed). Logged once via
  stderr.
- **Maestro running outside a git repo**: branch inference returns
  None; same as above.
- **Branch name contains issue number but doesn't match prefix
  pattern (e.g., `wip/64-foo`)**: regex miss; unattributed.
- **Explicit param + env var both set**: param wins, no warning
  (env wasn't used).
- **Explicit `task_id=""` or `issue_number=0`**: empty string and zero
  are treated as "user explicitly passed something falsy" — `task_id=""`
  → None; `issue_number=0` → 0 (recorded as-is; 0 is a legal int even
  though unusual). Schema-level validation could reject 0/negative,
  but the design prefers to accept and trust caller intent.

## Test plan

New unit tests (in `tests/test_dispatch_telemetry.py`):

| Test | Scenario | Expected |
|------|----------|----------|
| `test_emit_uses_explicit_param` | param only | row carries param values; no warning |
| `test_emit_param_overrides_env` | param + env | param wins; no deprecation warning |
| `test_emit_env_overrides_branch` | env only (in matching branch) | env wins; deprecation warning fires once |
| `test_emit_branch_inference` | no param, no env, branch matches | branch issue_number; task_id None |
| `test_emit_branch_inference_unmatched` | no param, no env, branch like `wip/x` | both None |
| `test_emit_unattributed_no_git` | no param, no env, subprocess fails | both None |
| `test_emit_deprecation_warning_one_shot` | env-driven dispatch ×3 | only first emits warning |
| `test_branch_re_patterns` | regex unit on `feature/N-`, `fix/N-`, `refactor/N-`, `docs/N-`, `wip/N-`, `feature/abc` | only first 4 match |

Integration tests (in `tests/test_workers.py`):

| Test | Scenario | Expected |
|------|----------|----------|
| `test_librarian_accepts_attribution_params` | dispatch with task_id+issue_number | row attributed correctly |
| `test_scribe_attribution_uses_existing_issue_number` | dispatch (existing test path) | row issue_number = required field's value |

Existing tests:
- `test_emit_records_task_id_when_env_set` — updated to assert
  deprecation warning fires.
- `test_emit_handles_invalid_issue_number_env` — unchanged.
- `test_scribe_rejects_non_integer_issue_number` — unchanged
  (scribe contract preserved).

## Out of scope (deferred)

- Removing env-var read path entirely (v0.0.4).
- Removing `scripts/begin_task.sh` file (v0.0.4).
- Refactoring scribe's required `issue_number / title / body` to be
  workflow-agnostic — tracked in `project_pure_worker_schemas.md`,
  likely Epic 7 scope.
- Adding a project-config file (e.g., `.maestro/current_task`) as
  another attribution source — judged unnecessary; the
  param/env/branch chain covers all observed cases.

## Migration notes

- Existing dogfooding sessions that rely on `begin_task.sh` will see
  the deprecation echo on next source. Their dispatches still work
  (env-var read continues), but the orchestrator should switch to
  parameter passing on next implementation task.
- New worker tools added in future epics get attribution for free if
  they accept the same optional params + call `_emit_dispatch_row`
  with them.
