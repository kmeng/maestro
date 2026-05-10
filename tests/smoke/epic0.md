# Epic 0 — end-to-end smoke checklist

This is the verification artifact for [Epic 0 #12](https://github.com/kmeng/maestro/issues/12).
Run before merging anything that touches the Web UI process or the MCP server's
shared-paths layer. Two parts:

1. **Automated** — `bash tests/smoke/epic0_smoke.sh` covers everything that
   doesn't need a browser or a Claude Code session.
2. **Manual** — visual rendering and the v0.0.2 regression need a human
   (browser + Claude Code).

## Acceptance criteria (from [issue #25](https://github.com/kmeng/maestro/issues/25))

- [ ] **AC1**: Clean-install smoke passes (`pip install -e .` → `maestro-webui` → page reachable). Covered by automated check 1–6.
- [ ] **AC2**: v0.0.2 regression — MCP `coder` from a Claude Code session still works with only a project-local `.env` and no `.maestro/` directory. Covered by manual section below.
- [ ] **AC3**: Port-conflict fallback — another process on `19830` causes `maestro-webui` to bind to `19831`. Covered by automated check 8.
- [ ] **AC4**: Documented checklist exists. (You're reading it.)

## Automated portion

```bash
bash tests/smoke/epic0_smoke.sh
```

Expected last line: `ALL AUTOMATED CHECKS PASSED`. Any `FAIL:` line in the output
is a regression — investigate before merging.

The script:

1. Reinstalls the package (`pip install -e .`)
2. Asserts `maestro-webui` console_script exists
3. Starts the launcher, parses the URL it prints
4. Verifies `GET /` returns 200 with the Chinese hero copy `等待第一支乐章`
5. Verifies `GET /static/vendor/htmx.min.js` returns 200 (vendored htmx, no CDN)
6. Verifies `GET /health` returns `{"status":"ok"}`
7. Cleans up the launcher and confirms the port is freed
8. Occupies `19830`, asserts `maestro-webui` falls back to `19831`

The script is timing-dependent on launcher startup (uvicorn cold-start, ~1s on
local dev). It polls the launcher's stdout for up to 10 seconds before
declaring failure — generous for any reasonable machine.

## Manual portion

### Browser visual (≈30s)

```bash
maestro-webui
# Open the printed URL in a browser
```

Verify:

- [ ] Hero copy `等待第一支乐章` is centered horizontally + vertically
- [ ] Eyebrow text `本地 AI 软件团队` appears above `Maestro` title
- [ ] Sub-copy `团队组建 · 项目脚手架 · 执行观测` and `将随 Epic 1–3 依次上演` are visible
- [ ] Footer `v0.0.3.dev0` (or current version) appears bottom-right
- [ ] Toggling OS dark/light mode flips the page (`prefers-color-scheme` adapt)
- [ ] DevTools network panel shows `/static/vendor/htmx.min.js` served from `127.0.0.1` (NOT a CDN host)

Stop the launcher with `Ctrl-C`.

### v0.0.2 regression — MCP `coder` from Claude Code (≈2 min)

The Web UI process must not have changed how Claude Code talks to the MCP
server. Smoke this by running an unmodified MCP `coder` call from a real
Claude Code session against a project that has only a local `.env` (no
`~/.maestro/credentials.env`, no `.maestro/` directory).

- [ ] In a Claude Code session, dispatch `coder` with any small spec (e.g.,
      "write a python function that returns 42"). Verify it returns code
      without errors.

`coder` is the v0.0.3 name for what was `cheap_code_gen` in v0.0.2 — both
references in older docs point to the same MCP tool. The rename happened in
T5.1 (Epic 5).

If this fails: the MCP server's path-resolution or env-loader changes from
T0.1 / T0.2 may have regressed v0.0.2 behavior — block the merge and bisect.

### Dev event emitter (≈10s)

Optional but recommended — confirms the developer affordance from T0.6 still
works end-to-end.

```bash
TMP=$(mktemp -d)
scripts/dev_emit_dispatch.py --project "$TMP"
scripts/dev_emit_dispatch.py --project "$TMP" --failure
cat "$TMP/.maestro/logs/dispatch.jsonl"
rm -rf "$TMP"
```

- [ ] Two JSON lines appear, one with `"outcome": "success"`, one with `"outcome": "failure"`

## When something fails

Don't paper over a `FAIL:` from the automated script. Common causes:

- **Port 19830 actually in use by something else** — the test will pass via fallback to 19831 in check 3, but check 8 will fail because it tries to occupy 19830 itself. Free 19830 and re-run.
- **Launcher times out** — uvicorn cold-start usually under 1s. >10s suggests an import chain regression in `maestro.webui` or `maestro.webui.launcher`.
- **HTML body grep miss** — someone changed the template's hero copy. Update the grep target in `epic0_smoke.sh` AND the AC table in this file together; don't silently desync.
- **htmx 404** — package data isn't being shipped. Check `[tool.setuptools.package-data]` in `pyproject.toml`.

When the automated script passes and manual checks pass, Epic 0 is end-to-end
green. Close [#25](https://github.com/kmeng/maestro/issues/25) and the parent
[Epic 0 #12](https://github.com/kmeng/maestro/issues/12).
