# Design: Epic 1 — team composition

**Issue**: #13
**Status**: draft

> Pass-1 draft. Establishes the user-visible flow and the role/member model.
> Config storage location and format, plus the schema for role-level model
> override, are deferred to v0.0.3 design pass 2.

## Problem

Through v0.0.2, configuring Maestro's team means editing config files by
hand. End users will not do this. Even Maestro's own maintainer has to
context-switch between docs and config. Epic 1 makes team composition a
guided visual flow that runs on top of Epic 0's empty-shell Web UI.

The flow has three pieces: a first-launch wizard that introduces Maestro's
team-composition model, a role catalog that lets the user see what each
role does and which model is bound to it, and member naming so the user
can refer to team members by friendly aliases.

## Out of scope

- Multiple members per role (1:N). v0.0.3 is 1 role : 1 member. 1:N is a
  vision-level open question (see #11 OPEN-V2) with a triggered-relax path,
  not an Epic 1 deliverable.
- Architect role instantiation. The Architect is the user's Claude Code
  main session. It is not a team member; it is the orchestrator that
  consumes Maestro. The role catalog shows Architect as a fixed identity
  ("you, via Claude Code"), not as something the user picks a model for.
- Member-level model override. Models bind to roles; aliasing a member
  does not let the user pick a different model for that member. Forbidden
  by design — relaxing this would defeat the simplicity of role-based
  dispatch.
- Per-task team composition. The team composition is the user's standing
  team for the project, not a per-invocation choice.
- Adding new roles beyond the four canonical ones (PM, Senior Engineer,
  Junior Engineer, Documentarian). New roles are an architectural decision
  outside Epic 1.

## Functional design

### First-launch wizard — four steps

When the Web UI detects no `team.yaml` for the active project (or when
the user re-enters the wizard from the menu), four linear steps:

**Step 1 — Welcome.** Plain-English orientation: what Maestro does,
what a "team" means, that the four roles work together, that Architect
(the user's Claude Code session) is **not** configurable here. No form
inputs. One button forward.

**Step 2 — Role catalog tour.** All four roles on one screen, in order
PM → Senior → Junior → Documentarian. For each role:

- A short description (1–2 sentences).
- An editable `model` field, pre-filled with the
  [`architecture.md`](../architecture.md) default. Curated dropdown of
  known model IDs plus a "custom…" escape hatch that flips to free
  text. Validation rules from D2 apply regardless of input source.
- An editable `member` field, pre-filled with a suggested alias (Alex /
  Sam / Jamie / Drew). User can accept, edit, or replace. Required.

Inline validation as the user types. "Next" button enabled only when
all four rows pass validation.

**Step 3 — Confirm.** Read-only summary of the four (role, member,
model) rows. Two buttons: **Save** (POST to `/api/team` → write
`team.yaml`) and **Back to edit** (returns to step 2 with current
values preserved).

**Step 4 — Done.** "Team saved" confirmation. Link to the standing
role-catalog view (where future row-by-row edits happen). Close button
returns the user to the Web UI's main page.

### Re-entry behavior

The wizard is **full-walk** every time. Re-entry from the menu loads
the current `team.yaml` values into step 2's form (instead of defaults)
and walks all four steps again.

Row-by-row "edit just this one thing" is the standing role-catalog
view's job, not the wizard's. Two surfaces, two purposes:

- **Wizard** = "I want to think about my whole team again."
- **Role catalog** = "I want to change one row."

### Cancel / back semantics

- A **Cancel** button is visible on steps 2 and 3 (not on step 1, not
  on step 4). Clicking cancel returns to the pre-wizard state with no
  writes — partial state is never persisted.
- The **Back** button on step 3 returns to step 2 with edits preserved
  in browser memory.
- The browser **back button** is treated as Cancel: discard, no write.

### Role catalog (standing view)

Outside the wizard, the role catalog is browseable as a permanent screen.
The user sees:

- The four instantiable roles + the Architect identity (informational only).
- For each instantiable role: assigned member name, bound model, and
  controls to edit either.

Edits are saved on confirmation, not on every keystroke.

### Member-level UI: name only

A member screen exists but contains nothing the user can change beyond the
member's display name. The model and the role are fixed by the role
binding. Surface this clearly so the user understands the model is a role
property, not a member property.

## Technical design

### Data model — schema (version 1)

`team.yaml` is YAML. Schema decided in pass 2; full rationale in
[ADR-0004](../adr/0004-team-config-format-and-schema.md).

```yaml
# Maestro team configuration. Edit via the Web UI.
# Run `maestro-webui`, then open http://localhost:19830/team
# Schema reference: docs/design/13-epic1-team-composition.md
schema_version: 1

roles:
  pm:
    member: Alex
    model: claude-sonnet-4-6
  senior:
    member: Sam
    model: claude-sonnet-4-6
  junior:
    member: Jamie
    model: deepseek-coder
  documentarian:
    member: Drew
    model: qwen-plus
```

Properties baked into the schema:

- **Role-keyed map** enforces 1 role : 1 member at the schema level —
  two PMs are not expressible.
- **All four roles required**, each with `member` and `model` fields,
  both required. No partial configs.
- **Defaults in code, not in file.** `architecture.md` defaults live in
  a `DEFAULT_MODELS` constant; the wizard pre-fills them; the file
  always carries explicit values.
- **Architect not included** — the user's Claude Code main session is
  not a configurable team member.
- **`schema_version: 1`** from day one for migration safety.

The schema is realized in code as Pydantic models (`TeamConfig`,
`RoleEntry`, `RoleId`). One contract serves Web UI I/O, YAML
round-trip, and MCP server read paths.

### Validation rules

The schema's Pydantic models enforce the rules below. Same models are
used at the Web UI form layer (inline error rendering), the API save
layer (422 responses with `field → message` maps), and the MCP server
read layer (read-failure → file-level fallback per D4).

**Per-field:**

| Field | Type | Rules |
|---|---|---|
| `schema_version` | int | Must be `1` for v0.0.3. Read-time rejection if absent or different; save-time rejection if the API caller claims another version. |
| `roles` | map | Keys must be exactly `{pm, senior, junior, documentarian}` — set equality, no extras, no missing. |
| `roles.<id>.member` | str | Required. Non-empty after whitespace strip. Max 64 chars. No newlines, tabs, or control characters. Unicode allowed. |
| `roles.<id>.model` | str | Required. Non-empty after strip. Matches `^[a-z0-9][a-z0-9._-]*$`. Max 128 chars. |

**Cross-field:**

- **Member alias uniqueness** — two roles cannot share a `member` value
  (case-insensitive, whitespace-trimmed comparison). Save rejected with
  a clear message ("Alex is already used as the PM's alias").
- **Role-set equality** — the `roles` map's key set must equal the four
  canonical IDs exactly.

**What's deliberately not validated at save time:**

- **Whether `model` corresponds to a real, callable model.** Maestro
  doesn't own the canonical list of valid model IDs; providers ship and
  retire models. The wizard offers a curated dropdown plus a custom
  escape hatch (UX detail in D3). At dispatch time, an unknown model ID
  surfaces in Epic 3's problem panel — that's the right discovery
  point, not config-save.
- **Whether credentials exist for the model's provider.** Same reasoning;
  runtime concern, not config-validity concern.

**Error reporting:**

- Web UI form: inline per-field error messages; submit button disabled
  while any field is invalid.
- API save (`POST /api/team`): Pydantic `ValidationError` → 422 with a
  structured `field → message` map; Web UI renders these inline.
- Read time: a `team.yaml` that fails validation triggers the file-level
  fallback (D4) — the file is **never** silently patched or partially
  accepted. Either the whole file passes or the system treats it as
  absent and surfaces the problem.

### Affected modules

- New: `maestro/team/` (or similar) — domain model for roles and members,
  config read/write.
- New: Web UI screens for the wizard, role catalog, member view.
- New: HTTP API endpoints under the Web UI for read/write of team config.
- Existing: MCP server `cheap_code_gen` invocation must be able to
  resolve "what model is bound to role X" by reading the same config. This
  is a small but real change in the MCP path: today the model is
  hard-coded / env-driven; in v0.0.3 it comes from the team config. This
  is the first place v0.0.3 actually affects the MCP runtime — handle with
  care to honor the no-regression rule.

### Failure modes (file level) — MCP-server fallback semantics

For any dispatch attempt, the project's `team.yaml` is in one of three
states. The MCP server's behavior, decided in pass-2 D4, is:

| State | MCP server behavior | Dispatch log event |
|---|---|---|
| Absent | Use v0.0.2 fallback (existing env-driven default model). Dispatch succeeds. | `dispatch.fallback.config_absent` (informational) |
| Present + valid | Resolve `roles.<role>.model` from `team.yaml`. Dispatch with that model. | normal start/end events (Epic 3) |
| Present + **invalid** | **Refuse the dispatch.** Return a structured error to Claude Code naming the failing field. **No silent fallback.** | `dispatch.refused.config_invalid` with validation detail |

**Why "absent → fallback" but "invalid → refuse" are not symmetric.**
A user with no `team.yaml` has not opted into v0.0.3 team configuration —
possibly a v0.0.2 user who hasn't run the wizard yet. Falling back
honors that intent: zero-regression. A user with an *invalid*
`team.yaml` has tried to configure a team and gotten it wrong. Silently
falling back would hide the bug ("why is my Junior using
claude-sonnet-4-6? I configured deepseek-coder!") and violate D1's
explicit-over-implicit principle. Refusing makes the failure visible
immediately; the user fixes the file and retries.

**Error message shape on refuse:**

> `team.yaml at .maestro/team.yaml is invalid: roles.junior.model — must match pattern '^[a-z0-9][a-z0-9._-]*$'. Open the Web UI to fix, or edit the file directly.`

The same error is written as a `dispatch.refused.config_invalid` event
so Epic 3's problem panel surfaces it on next Web UI load.

**Atomic writes for Web UI saves.** The Web UI writes `team.yaml` via
`write-then-rename` (`os.replace`) so the MCP server can never observe
a partially-written file. Without atomicity, a concurrent dispatch
during a save could read torn YAML, fail validation, and produce a
spurious "config invalid" refusal. With atomicity, the MCP server sees
either the old file or the new file — never an in-between state.

**Edge cases:**

- *Partial config (user filled in 2 of 4 roles by hand-editing).* Fails
  D2's strict-completeness rule → invalid → refused. The wizard guarantees
  completeness on every save, so this is only reachable via manual edits.
- *Role isn't dispatched in v0.0.2/v0.0.3 yet.* Only Junior is dispatched
  today (`cheap_code_gen`). Other roles in `team.yaml` are ignored at
  dispatch time and consumed when their corresponding workers exist
  (post-v0.0.3). They still must be present and valid in the file —
  D1's strict-completeness rule isn't relaxed.

**Two new dispatch-log event types** (`dispatch.fallback.config_absent`
and `dispatch.refused.config_invalid`) need to be incorporated into the
log schema Epic 3's pass-2 lands. Flagged in Epic 3's open questions.

## Task breakdown

PR-sized closed loops. Each PR keeps `main` runnable. Order is the
dependency order. **Prerequisite**: all of Epic 0 T0.1–T0.4 must be
landed before T1.1 starts.

- [ ] **T1.1** — Add Pydantic models (`TeamConfig`, `RoleEntry`, `RoleId`) per [ADR-0004](../adr/0004-team-config-format-and-schema.md), plus a `DEFAULT_MODELS` constant sourced from [`architecture.md`](../architecture.md). Pure data model. Unit tests on the validators (D2 rules: regex, length caps, role-set equality, alias uniqueness). (~1.5h)
- [ ] **T1.2** — YAML read/write helpers in `maestro/team/`. Read returns `TeamConfig | None | ValidationError`; write uses `os.replace` for atomic write-then-rename. Wired up by a no-op load from the MCP server's startup path so the module isn't orphaned. Unit tests on round-trip + atomicity. (~1.5h)
- [ ] **T1.3** — HTTP API endpoints: `GET /api/team` (404 if absent, 200 on valid, 422 with field-map on invalid) and `POST /api/team` (201 on success, 422 on validation error). Unit tests per response code; smoke: curl flow. (~1h)
- [ ] **T1.4** — Wizard UI: four steps (Welcome / Role tour / Confirm / Done). Inline validation. Cancel/Back semantics. Pre-fills from `architecture.md` defaults on first launch; from existing `team.yaml` on re-entry. Smoke: walk through wizard end-to-end on clean state and on re-entry. (~2h)
- [ ] **T1.5** — Standing role-catalog view: read-only summary of saved team plus per-row edit. The non-wizard surface for changing one row. Smoke: edit one row, confirm `team.yaml` updated. (~1.5h)
- [ ] **T1.6** — Wire MCP server's `cheap_code_gen` to resolve Junior's `model` from `team.yaml` per D4: absent → v0.0.2 fallback; valid → use config; invalid → refuse with structured error. Emit `dispatch.fallback.config_absent` and `dispatch.refused.config_invalid` events. Unit tests on all three branches; smoke: clean install with `.env` only still works exactly as v0.0.2. (~1.5h)
- [ ] **T1.7** — End-to-end verification PR. Documented manual smoke: wizard → use configured model → break `team.yaml` → refuse cleanly → fix → works. Plus regression: `.env`-only project still works as v0.0.2. (~1h)

## Acceptance criteria

- A first-time user with no prior Maestro config can complete the
  first-launch wizard end-to-end and produce a valid team config.
- The role catalog standing view reflects the saved config and can edit
  it.
- A `cheap_code_gen` invocation after team composition uses the model
  bound to the configured role.
- A `cheap_code_gen` invocation **before** any team composition still
  works (v0.0.2 fallback path), with a clear log indication that fallback
  was used.
- The Architect identity is shown in the catalog but cannot be edited or
  bound to a model.
- Member-level UI does not expose a model field. Attempting to set one via
  the API is rejected.

## Open questions

- ~~**OPEN-1.1.** Config storage location.~~ **Resolved by Epic 0 pass-2**: project-local `<project-root>/.maestro/team.yaml` (committed by default). User-global config home (`~/.maestro/`) is reserved for credentials, the recent-projects registry, and user preferences — not team composition. See [ADR-0003](../adr/0003-shared-state-file-layout.md).
- ~~**OPEN-1.2.** Config format — YAML vs JSON.~~ **Resolved**: YAML, via `pyyaml` — see [ADR-0004](../adr/0004-team-config-format-and-schema.md).
- ~~**OPEN-1.3.** Schema-level shape of role-level model override.~~ **Resolved**: no separate "override" mechanism. The user simply sets `model:` to whatever they want. Defaults pre-filled by wizard, never implicit. See [ADR-0004](../adr/0004-team-config-format-and-schema.md).
- ~~**OPEN-1.4.** First-launch wizard re-entry.~~ **Resolved**: full re-walk every time, with current values pre-filled. The standing role-catalog view handles row-by-row edits; the wizard is the "think about my whole team" surface. Detail in the wizard subsection above.
- **OPEN-1.5.** 1:N triggers. When v0.0.3's 1:1 limit is felt as a
  constraint by users (or by Maestro itself dogfooding), what does the
  data model migration look like? Captured here for visibility — actual
  resolution happens in a future post-v0.0.3 design round.
