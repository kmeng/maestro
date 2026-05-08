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

### First-launch wizard

The first time the user opens Maestro's Web UI in a project (or globally —
location of the config home is OPEN), the Web UI detects there is no team
config and walks the user through a wizard:

1. **Introduction.** What Maestro does. What "the team" means. That
   Architect is the user's Claude Code session, not a team member.
2. **Role catalog tour.** Show the four instantiable roles, each with: a
   short description, the default model bound to it (per
   `architecture.md`), and an editable "model" field if the user wants to
   override at the role level.
3. **Member naming.** For each role, the user gives the member a name
   (e.g., the PM is "Alex"). One member per role in v0.0.3. Default names
   may be offered.
4. **Confirmation.** Show the resulting team. Save.

Re-running the wizard from the menu later edits the existing team rather
than creating a new one.

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

### Data model — coarse

Two layers of config:

- **Role layer.** Four entries, one per instantiable role. Each entry:
  role identifier (`pm`, `senior`, `junior`, `documentarian`), bound model
  identifier (e.g., `claude-sonnet-4-6`, `deepseek-coder`), optional
  user-supplied display name override for the role.
- **Member layer.** One entry per role in v0.0.3 (the 1:1 constraint).
  Each entry: member identifier, role reference, user-chosen alias.

The Architect identity is not in the config — it's implicit (the running
Claude Code session). The role catalog UI shows it for completeness but
the config layer ignores it.

The actual schema (YAML vs JSON, field names, validation rules) is pass-2
work.

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

### Failure modes

- **Config file missing.** Web UI shows the first-launch wizard. MCP
  server, if invoked before config exists, falls back to its v0.0.2
  default behavior (current env-driven model selection) and logs a
  warning the Web UI can later surface in the problem panel (Epic 3).
  This is the no-regression escape hatch.
- **Config file corrupted / unreadable.** Web UI shows a "fix or reset"
  screen rather than auto-overwriting. MCP server falls back as above.
- **Model identifier in config doesn't match a known model.** Validate at
  save time in the Web UI; MCP server validates at read time and falls
  back as above with a clear log line.
- **Two members with the same alias.** v0.0.3 has one member per role,
  so duplicate aliases come from user typo. Validate at save time.

## Task breakdown

High-level milestones.

- [ ] T1.1 — Pass-2 design: config storage location (~/.maestro/ vs project-local vs hybrid) — joint with Epic 0 OPEN-0.4
- [ ] T1.2 — Pass-2 design: config schema (YAML vs JSON, field names, validation rules)
- [ ] T1.3 — Implement: team domain model + read/write of config
- [ ] T1.4 — Implement: HTTP API endpoints for team config
- [ ] T1.5 — Implement: Web UI first-launch wizard
- [ ] T1.6 — Implement: Web UI role catalog standing view
- [ ] T1.7 — Implement: MCP server reads role→model binding from config, with v0.0.2 fallback when config absent
- [ ] T1.8 — Verify: end-to-end. New install → wizard → cheap_code_gen invocation uses the configured model.

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

- **OPEN-1.1.** Config storage location. Three candidates: `~/.maestro/`
  (per-user, all projects share a team), project-local `.maestro/`
  (per-project teams, per-project model bindings), or a hybrid (defaults
  in `~/.maestro/`, overrides per project). Joint decision with Epic 0
  OPEN-0.4. Pass-2 ADR.
- **OPEN-1.2.** Config format — YAML vs JSON. YAML is friendlier to manual
  inspection; JSON has fewer parsing edge cases and matches existing
  Python ecosystem more cleanly. Pass-2 decision.
- **OPEN-1.3.** Schema-level shape of role-level model override. Specifically,
  what's the override mechanism's UX and config representation when the
  user wants role X to use a model different from `architecture.md`'s
  default? Pass-2 design.
- **OPEN-1.4.** First-launch wizard re-entry. Should re-running the wizard
  from the menu walk through all steps again, or jump to the first
  unfilled / unconfirmed step? Pass-2 UX call.
- **OPEN-1.5.** 1:N triggers. When v0.0.3's 1:1 limit is felt as a
  constraint by users (or by Maestro itself dogfooding), what does the
  data model migration look like? Captured here for visibility — actual
  resolution happens in a future post-v0.0.3 design round.
