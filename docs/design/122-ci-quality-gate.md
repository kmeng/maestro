# Design: ruff + pytest CI quality gate (Phase B)

**Status**: draft (awaiting approval)
**Issue**: #122
**Related**: `docs/journal/2026-05-17-epic10-v0.1.0-ship.md` (Phase B origin), `docs/roadmap-v1.md` Bucket 2
**ADR**: not required — dev-only tooling (a linter + a CI workflow). No new shipped interface, storage format, or worker role; fully reversible (delete the workflow + config). The "new dependency" ADR trigger is scoped to runtime/shipped deps; `ruff` is a dev-only dependency.

## Problem

Lint and test regressions are currently caught only by contributor discipline + memory recall (an L4/L5 defense — see the rule-maturity framing in CODE-2026-05-19-002). There is no deterministic, harness-level gate. pytest exists and is green (568 passed today) but nothing runs it automatically; no linter is configured at all.

This is Phase B from the Epic 10 close — deferred when the user chose "ship v0.1.0" over "CI gate." It is the last open item in v1.0 roadmap Bucket 2 ("No bug debt").

## Functional design (what contributors experience)

- On every **push to a dev branch (`v*`) or `main`**, and on every **pull request**, GitHub Actions runs `ruff check` + `pytest`. A failure shows as a red check on the commit / PR in the GitHub UI.
- **Local parity**: `ruff check .` and `pytest` reproduce CI exactly — same pinned `ruff` version, same config in `pyproject.toml`. A contributor never sees "passes locally, fails in CI" from tooling drift.
- The gate is **silent on green** — no friction on passing work.

### Why these triggers (project-specific)

Maestro's branch workflow (`feedback_branch_workflow`) merges feature branches **locally** into the dev branch and pushes the dev branch — there are **no feature→dev PRs**. PRs exist only for `dev→main` releases. A conventional `pull_request`-only gate would therefore almost never fire (only at release). To gate day-to-day work, the gate must trigger on **`push` to `v*` and `main`**. `pull_request` is kept too, so release PRs are also gated.

Tag pushes (`v0.1.0` etc.) are handled by `release.yml` and do **not** match `on.push.branches` (tags are `refs/tags/*`, not branches), so there is no double-run.

**Branch-pattern note (2026-05-22)**: an earlier draft used `'v[0-9]+.[0-9]+*'`. Both the `coder` and the `reviewer` worker flagged the `+` glob as risky — GitHub Actions filter patterns do list `+` as special ("one or more of the preceding character"), but its behavior is easy to get wrong and a mismatch fails *silently* (the gate just never fires — the worst outcome for a gate). Resolved by switching to **`'v[0-9]*'`**, which uses only the unambiguous `[]` + `*` globs, requires a digit after `v` (so it won't match `vendor`/`vanity`-style branches), and matches every `v<major>.<minor>` dev branch. To be verified empirically on the first real push to `v1.0`.

## Technical design

### New workflow `.github/workflows/ci.yml`

```yaml
name: CI

on:
  push:
    branches:
      - main
      - 'v[0-9]*'   # dev branches: v1.0, v1.1, v2.0, ...
  pull_request:

permissions:
  contents: read

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true   # superseded pushes don't stack runs

jobs:
  quality:
    name: ruff + pytest
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'   # matches release.yml
      - name: Install
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"
          pip install -r bootstrap/requirements.txt   # MCP-server deps (mcp, openai)
      - name: Ruff
        run: ruff check .
      - name: Pytest
        run: pytest -q
```

**Dependency completeness (caught by the gate's first real run, 2026-05-22)**: the first CI run on `v1.0` went red — the gate immediately earned its keep by surfacing **undeclared dependencies** that pass locally only because the dev's venv happened to have them:
- `python-multipart` — required at import time to register the webui FastAPI form route (so `import maestro.webui` fails without it). A genuine **runtime** dep; added to pyproject `dependencies`. (Latent shipping gap: a clean `pip install maestro` + `maestro webui` would have failed; the release smoke doesn't exercise webui forms so it never caught this.)
- `httpx` — required by `fastapi.testclient.TestClient` in the webui tests; test-only, added to `[dev]`.
- `mcp`, `openai` — the MCP server's core deps live in `bootstrap/requirements.txt` (a deliberate split from pyproject, per the binary-build flow), so the CI install step mirrors `release.yml` and installs them too.

- **Python 3.11** to match `release.yml`. (A `[3.10, 3.11]` matrix to test the `requires-python` floor is a possible follow-up; single version keeps v1.0 cost/scope down.)
- Action versions `checkout@v4` / `setup-python@v5` — current (no Node-deprecation issue; that roadmap item concerns other repos/workflows, not this one).
- `concurrency` cancels superseded runs on rapid pushes to the same ref.

### `pyproject.toml` changes

```toml
[project.optional-dependencies]
dev = [
    "pytest",
    "pytest-asyncio>=0.21",
    "ruff==0.15.14",        # pinned: new ruff minors add rules; bumps are deliberate
]

[tool.ruff.lint]
# ruff's default ruleset (pycodestyle E4/E7/E9 + pyflakes F), made explicit
select = ["E4", "E7", "E9", "F"]
```

- **Pin `ruff` exactly** so the gate is deterministic — a ruff minor bump can introduce new rules that turn the gate red without any code change. Bumps become an intentional PR.
- `select = ["E4", "E7", "E9", "F"]` is **ruff's actual default** ruleset, stated explicitly to document intent and make future expansion a visible diff. **Correction (2026-05-22)**: an earlier draft wrote `select = ["E", "F"]` and called it "the default" — that is wrong. The bare `"E"` category enables the *entire* pycodestyle error set (E1/E2/E3/E5…), notably **E501 line-too-long**, which floods the repo with violations far beyond the measured 43-violation scope this work was approved for. Ruff's documented default is `["E4", "E7", "E9", "F"]` (which is what the 43-violation baseline was measured against). The config matches that default exactly.
- `ruff` added to the **`dev`** extra so `pip install -e ".[dev]"` gives local == CI. (`requirements-dev.txt` is left as-is or can mirror; the `[dev]` extra is the source of truth the workflow uses.)

### Pre-requisite cleanup — 43 existing violations

The gate must land **green**, so the existing violations are resolved in the same closed loop:

| Code | Count | Nature | Fix |
| --- | --- | --- | --- |
| F401 unused-import | 32 | mechanical | `ruff check . --fix` (deterministic autofix) |
| E402 module-import-not-at-top | 3 | judgment | restructure, or `# noqa: E402` where a pre-import side-effect (e.g. `sys.path`) is intentional |
| E741 ambiguous-variable-name | 3 | judgment | rename (`l`/`I`/`O` → descriptive) |
| F402 import-shadowed-by-loop-var | 3 | judgment | rename the loop variable |
| F841 unused-variable | 2 | judgment | remove, or use |

Distribution (approx): `tests/` ~28, `maestro/` ~11, `scripts/` ~4.

### Failure modes

| Failure | Effect | Mitigation |
| --- | --- | --- |
| ruff minor bump adds rules | gate goes red with no code change | exact version pin; bumps are deliberate PRs |
| Lint scope catches `.venv`/build dirs | noise / false failures | ruff auto-excludes `.venv`, `dist`, `build`, `__pycache__`; no extra config needed |
| `conftest.py` autouse subprocess patch | tests behave same in CI as locally | already the case — CI just runs `pytest`, no change |
| Contributor lacks `ruff` locally | local/CI drift | `ruff` in `[dev]` extra + pinned; documented in ops pointer |

## Task breakdown (closed loops)

This is small and the parts are coupled (a workflow without a clean repo = a red gate on landing), so it is **one closed loop / one PR**:

1. Resolve the 43 ruff violations (autofix + manual).
2. Add `[tool.ruff.lint]` config + pinned `ruff` dev dep.
3. Add `.github/workflows/ci.yml`.
4. Verify locally: `ruff check .` clean + `pytest` green.
5. Land on `v1.0`; confirm the gate runs green on the real push.

`main` stays green throughout because the cleanup + config + workflow land together.

### Dogfooding dispatch plan (per `feedback_coder_file_modification` / `feedback_dogfooding_implementation`)

Code-producing work dispatches to `coder`, not the orchestrator:

- **32 F401 autofix** — `ruff check . --fix` is a deterministic tool run, not authoring → orchestrator runs it directly (mechanical, like a formatter).
- **11 manual fixes + `ci.yml` + `pyproject.toml` edits** — these are authored code/config/templates → **dispatch `coder`** with a precise spec (exact files, exact violations, exact workflow content from this doc). Diff-check the coder output against current files before applying (`feedback_coder_full_file_diff_check`), then **`reviewer` pass before merge** (`feedback_shadow_mode_active` — promoted ≠ optional).

**Decided at approval (2026-05-21)**: `coder` authors the net-new/structured artifacts — `ci.yml` (new file) and the `pyproject.toml` edits (add `[tool.ruff.lint]` + pinned `ruff` dev dep). The 11 manual lint fixes are tiny one-liners scattered across existing source/test files, so the **orchestrator applies those inline** alongside the mechanical `ruff --fix`. `coder` output is diff-checked before apply (`pyproject.toml` is an existing file — apply surgically per `feedback_coder_full_file_diff_check`); `reviewer` pass before merge.

## Acceptance criteria (mirrors #122)

- [ ] `.github/workflows/ci.yml` runs ruff + pytest on push(`v*`/`main`) + PR
- [ ] `[tool.ruff.lint]` config in `pyproject.toml`; `ruff` pinned in `[dev]`
- [ ] All 43 existing violations resolved; `ruff check .` clean
- [ ] `pytest` green in CI
- [ ] One-line ops pointer documented (`docs/ops/`)
- [ ] Gate verified green on a real push to `v1.0`
- [ ] `docs/roadmap-v1.md` Bucket 2 corrected (smoke `#104` done vs CI gate `#122`)
