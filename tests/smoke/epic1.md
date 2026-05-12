# Epic 1 — Team Composition: End-to-End Smoke

This is the verification artifact for [Epic 1 #13](https://github.com/kmeng/maestro/issues/13).
Run before merging anything that touches `maestro/team/`, `maestro/webui/wizard.py`,
`maestro/webui/team_catalog.py`, `maestro/webui/team_api.py`, or the worker
team-resolution path in `bootstrap/maestro_server.py`. Two parts:

1. **Automated** — `bash tests/smoke/epic1_smoke.sh` covers everything that
   doesn't need a browser or a Claude Code session.
2. **Manual** — visual wizard walkthrough and the cross-process MCP
   `coder` regression need a human (browser + Claude Code).

## Quick check: automated portion

```bash
bash tests/smoke/epic1_smoke.sh
```

Expected last line: `ALL AUTOMATED CHECKS PASSED`. Any `FAIL:` line in the
output is a regression — investigate before merging.

The script:

1. Reinstalls the package (`pip install -e .`)
2. Starts a `maestro-webui` instance with `cwd` set to a fresh temp project
   directory (so `.maestro/team.yaml` is isolated from any real project)
3. Walks the wizard end-to-end via HTTP (welcome → step 2 defaults → field
   validation → step 3 confirm → save persists)
4. Round-trips the config via `GET /api/team`
5. Walks the standing role catalog (`GET /team` table; `POST /team/edit/coder`
   updates a row)
6. Hand-breaks `.maestro/team.yaml`, asserts `GET /api/team` returns 422 and
   `GET /team` shows the Chinese invalid-config banner
7. Restores a valid config via `POST /api/team` (JSON body); asserts recovery
8. Kills the server, asserts the port is freed

## Acceptance criteria — automated

- [ ] **Wizard welcome page renders.** (smoke check 3)
- [ ] **Wizard step 2 prefills defaults on a fresh project.** (smoke check 4)
- [ ] **Inline field validation returns Chinese error.** (smoke check 5)
- [ ] **Wizard step 3 accepts valid input and shows confirmation.** (smoke check 6)
- [ ] **Wizard save persists `team.yaml`.** (smoke check 7)
- [ ] **`GET /api/team` round-trips the saved configuration.** (smoke check 8)
- [ ] **`GET /team` renders the role catalog with saved values.** (smoke check 9)
- [ ] **`POST /team/edit/<role>` updates a single row and persists.** (smoke check 10)
- [ ] **Hand-broken `team.yaml` causes `GET /api/team` to return 422.** (smoke check 11)
- [ ] **Broken `team.yaml` causes `GET /team` to show invalid-config banner.** (smoke check 12)
- [ ] **Restoring a valid `team.yaml` recovers `GET /api/team` to 200.** (smoke check 13)
- [ ] **Server kills cleanly and releases its port.** (smoke check 14)

## Acceptance criteria — manual

These require either a browser or a real Claude Code session and so are not in
the automated script.

### Browser walkthrough of wizard (≈1 min)

```bash
maestro-webui
# Open the printed URL/wizard in a browser
```

- [ ] All 4 steps transition correctly: Welcome → Role tour → Confirm → Done.
- [ ] Chinese copy renders without mojibake (system fonts, dark/light mode
      both readable).
- [ ] Inline field validation appears on blur (try entering `DeepSeek-V4` in a
      model field — Chinese error should appear next to the field).
- [ ] After Save, `.maestro/team.yaml` exists in the launching directory and
      its content matches the wizard form.

### `/team` standing view (≈30s)

- [ ] The architect row shows the Chinese copy "你的 Claude Code 主会话" and
      has no edit button.
- [ ] Clicking "编辑" on a non-architect row swaps the row in-place with
      `member` and `model` inputs and "保存" / "取消" buttons.
- [ ] "保存" persists the change; "取消" reverts to the pre-edit values
      without writing.

### MCP `coder` regression — three scenarios (≈3 min, requires Claude Code)

For each scenario, run a real Claude Code session pointing at a test project
directory, then dispatch `mcp__maestro__coder` with a small spec
(e.g., "write a Python function that returns 42").

- [ ] **No `team.yaml` (v0.0.2 fallback path):** project directory has no
      `.maestro/team.yaml`. Dispatch coder. Verify the response is normal
      (no refusal text). Inspect `<project>/.maestro/logs/team_events.jsonl`;
      it should contain a `dispatch.fallback.config_absent` event with
      `model: deepseek-v4-pro`.

- [ ] **Wizard-completed project:** complete the wizard with a valid config
      (use the default values for simplicity). Dispatch coder again. Verify
      the model the worker used matches the configured `roles.coder.model`.
      No `dispatch.fallback.*` event for this call (Epic 3 will own normal
      start/end events; the absent-config event explicitly does not fire on
      the valid path).

- [ ] **Hand-broken `team.yaml`:** manually write `: : :` (or any invalid
      content) to `.maestro/team.yaml`. Dispatch coder. Verify the response
      text starts with `team.yaml at .maestro/team.yaml is invalid:` and
      includes a hint to open the Web UI. Inspect `team_events.jsonl`; it
      should contain a `dispatch.refused.config_invalid` event with the
      role and a `detail` summarising the validation failure.

### Member-level UI does NOT have a model field (≈10s)

- [ ] On the `/team` catalog page, there is no separate "member" screen
      offering an independent model setting. The model is a role property,
      edited only through the role's row. (Design §13 explicitly forbids a
      member-level model override.)

## When something fails

Don't paper over a `FAIL:` from the automated script. Common causes:

- **Port already in use** — `maestro-webui` falls back to 19831, etc.
  The smoke checks parse the URL from the launcher's log, so they follow
  the fallback. If you see `did not output URL` instead, the launcher
  may have failed to start at all — re-run with verbose log capture.
- **Wizard endpoint 422 / 4xx on valid form data** — the form field
  names diverged. The script uses `member_<role>` and `model_<role>`
  (role as suffix). If `maestro/webui/wizard.py` changes the field naming
  convention, update the script and the wizard templates together.
- **`GET /api/team` doesn't return 422 on broken file** — `maestro/team/io.py`
  must distinguish absent (None) from invalid (TeamConfigInvalid). Inspect
  what `load_team_config` returns and trace the 404 vs 422 branch in
  `maestro/webui/team_api.py`.
- **`/team` Chinese banner missing** — template literal divergence.
  The smoke greps `team.yaml 配置无效`; the template must contain that
  exact substring.
- **Port not freed after kill** — uvicorn's graceful shutdown is mostly
  reliable; on some systems a small delay (currently 0.5s) is needed
  before the rebind check. If this is flaky on CI, increase the sleep.

When the automated script passes and all manual checks pass, Epic 1 is
end-to-end green. Close [#32](https://github.com/kmeng/maestro/issues/32)
and the parent [Epic 1 #13](https://github.com/kmeng/maestro/issues/13).
