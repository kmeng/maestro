# CI quality gate

`.github/workflows/ci.yml` runs `ruff check .` + `pytest -q` on every push to
`main` or a dev branch (`v*`), and on every pull request.

**Local parity** (reproduce CI exactly before pushing):

```bash
pip install -e ".[dev]"   # installs the pinned ruff + pytest
ruff check .
pytest -q
```

`ruff` is pinned in the `[project.optional-dependencies] dev` extra and its
ruleset lives in `[tool.ruff.lint]` (`pyproject.toml`) — the default
`E4/E7/E9 + F` set. A `ruff` version bump is deliberate (it can introduce new
rules), so change the pin in its own change.
