# Design: governance amendment — task tracking via sub-issues + implementation-start protocol

**Issue**: #17
**Status**: draft

> Word-for-word capture of the wording changes to CLAUDE.md and
> governance.md, plus a small new design doc convention. The
> implementation PR (#17 follow-up) is mechanical: paste the approved
> text into the protected docs.

## Problem

Restated from #17. Today's CLAUDE.md and governance.md prescribe
"tasks tracked as checkboxes in the GitHub issue body." This worked
through v0.0.2; v0.0.3's design phase produced 33 PR-sized tasks
across four epics — past the scaling point for checkboxes. Concrete
gaps:

- Tasks lack individual issue ids → PRs cannot `Closes #N` an
  individual task.
- Cross-task progress requires opening every epic body.
- Bug-to-task linkage lives in PR text, not in the issue graph.
- AI implementers (cold-start every session) lack a discrete,
  self-sufficient briefing per task; context recovery means re-reading
  entire epic bodies each time.

The deeper concern: the v0.0.3 design pass produced 7 ADRs + 5 design
docs + 33 task slots in a single day. That information density is at
risk of degrading as we move to coding unless the task-level briefing
surface is strong.

## Out of scope

- Verifying `gh` CLI's sub-issue support in detail. Already done in
  the spike: `gh` 2.89.0 has no `sub-issue` subcommand; `gh api` calls
  to `/repos/{owner}/{repo}/issues/{n}/sub_issues` work. Documented
  for the script step, not for governance.
- Migrating the existing 33 v0.0.3 task checkboxes into sub-issues —
  separate issue + PR, scheduled after this lands.
- Defining labels (`epic`, `task`, `bug`, `v0.0.3`). The repo has no
  label scheme today; adding one is a separate housekeeping issue.
- README.md changes. Reader-visible workflow lives in governance.md;
  README doesn't need to know.

## Functional design

After this change merges, contributors (human + AI) experience the
following:

### Creating a task

A task lives as a **sub-issue under its parent epic**. The sub-issue
body follows the briefing template (defined in governance.md §
Task tracking). The body is the *task's contract* — it states the
goal, the design references, the acceptance criteria, and the test
plan, in a self-sufficient form so that an implementer can start
without opening the epic body.

### Implementing a task

When the user (or AI maintainer dispatch) asks Claude Code to
"implement task #N":

1. Claude Code reads the sub-issue body (mandatory; this is the new
   Implementation-start protocol).
2. Claude Code opens every `§design` and `§ADR` link in the briefing
   and reads them.
3. Claude Code states the implementation plan back, mapping each
   acceptance criterion in the briefing to a "covered by approach X"
   line.
4. The user says `go`; coding begins.

### Closing a task

The PR for task #N includes `Closes #N` on its own line, plus the
strengthened PR description requirements (Implements / Design citation
/ acceptance-criteria checklist). On merge, GitHub auto-closes the
sub-issue. The parent epic's "N of M sub-issues completed" counter
updates automatically.

### Logging a bug

A bug found during or after implementation gets its own independent
issue, labeled (when labels exist) `bug`, body includes provenance
(`Found while implementing #<task>`) and links back to the originating
task or epic. The existing bug-fix protocol applies: failing test
first, fix second.

## Technical design

### CLAUDE.md changes

Two edits, both additive within the existing document structure.

#### Edit C1: Insert the Implementation-start protocol

**Location**: after the existing "Session-start protocol" section
(ends at line ~24), before "Project context" (begins at line 28).

**New text to insert** (between the existing `---` separators at
those positions):

```markdown
## Implementation-start protocol

Before writing any code for an implementation task, you MUST:

1. Run `gh issue view <task-issue-number>` and read the full task briefing.
2. Open every link in the task body's "Design references" section — design doc sections (`§design`) and ADRs (`§ADR`) are mandatory reading; the parent epic is mandatory reading.
3. State the implementation plan back to the user, mapping each acceptance criterion in the briefing to "covered by approach X" with one short sentence per criterion.
4. Wait for the user's explicit `go` (or equivalent) before writing code.

This protocol applies whenever a request can be traced to an existing task issue. If the user asks for code without referencing an issue, ask which task it corresponds to before proceeding.

The point of mandatory pre-reading: AI implementers start cold every session. Rich, mandatory-reading briefings are the difference between on-target implementation and "close enough but missing constraint X."
```

#### Edit C2: Replace task tracking line in workflow step 3

**Location**: section "## Mandatory workflow for any change", subsection
"### 3. Break tasks into closed loops" (around line 56).

**Existing text** (last bullet of the subsection):

```
- Track tasks as checkboxes in the GitHub issue
```

**Replacement text**:

```
- Track tasks as **sub-issues under the parent epic**. Each sub-issue body follows the briefing template in [`docs/governance.md` § Task tracking](docs/governance.md#task-tracking). Checkboxes inline in the parent issue body are no longer used for task tracking.
```

### governance.md changes

Three edits.

#### Edit G1: Update lifecycle step 5 (BREAKDOWN)

**Location**: section "## Lifecycle of any change", inside the ASCII
flow diagram (around line 25).

**Existing text** (in the diagram):

```
5. BREAKDOWN    Split into small closed loops, ~30min–2h each
                → tracked as checkboxes in the issue
```

**Replacement text**:

```
5. BREAKDOWN    Split into small closed loops, ~30min–2h each
                → tracked as sub-issues under the epic; each
                  sub-issue body follows the briefing template
                  (§ Task tracking)
```

#### Edit G2: Insert new "Task tracking" section

**Location**: a new top-level section, inserted between "## The
Closed Loop Rule (核心)" (ends around line 59) and "## Branch and
commit conventions" (begins around line 61).

**New section text**:

````markdown
---

## Task tracking

Tasks live as **sub-issues under their parent epic**. GitHub's
sub-issues feature (GA 2025) provides parent→child issue hierarchy
natively — the parent issue auto-displays "N of M sub-issues
completed," each sub-issue has its own id and can be closed
independently by `Closes #N` in a PR.

### Briefing template

Each sub-issue body follows this template. The body is the *task's
contract*; PRs satisfy it.

```markdown
## Goal

[One paragraph: what this task achieves once merged.]

## Design references (mandatory reading)

- §design: [docs/design/<file>.md — § Section name]
- §ADR: [docs/adr/<file>.md — § Section name]
- Parent epic: #<epic-issue-number>

## Scope

What this task does:
- [...]

What this task explicitly does not do:
- [...]

## Acceptance criteria

- [ ] [Enumerated, testable criterion 1]
- [ ] [Enumerated, testable criterion 2]
- ...

## Test plan

- Unit: [test file paths and what they cover]
- Smoke: [manual verification steps where applicable]

## Estimate

~Nh

## Dependencies

- None / #<other-task> / [list]
```

### Creating sub-issues

`gh` CLI (as of 2.89.0) does not have a `gh sub-issue` subcommand.
Sub-issue creation uses `gh api` against the REST endpoint
`POST /repos/{owner}/{repo}/issues/{parent}/sub_issues` with the
child issue's internal `id` (not its number). A small helper script
(e.g., `scripts/create_subissue.sh`) is the recommended path; the
script body is workflow tooling, not governance content.

### What checkboxes are still for

Checkbox lists inside an issue or design-doc body are still used for
**acceptance criteria** within a single sub-issue's briefing, and for
**Definition of Done** within a single PR's description. They are no
longer used for task lists across multiple PRs — that role belongs to
sub-issues.
````

#### Edit G3: Strengthen "Pull Request rules"

**Location**: section "## Pull Request rules" (around line 129).

**Existing text** (the bullet list at the top of the section):

```
- One PR = one closed loop
- PR description must include: linked issue, what changed, how to verify
- Squash-merge to main; no merge commits in main
- PR > 400 lines: justify in the description or split
```

**Replacement text**:

```
- One PR = one closed loop = one task sub-issue closed
- PR description must include:
  - `Implements: #<sub-issue-number>` (the task being closed)
  - `Closes #<sub-issue-number>` on its own line in plain prose (per the auto-close phrasing rule below)
  - `Design citation: docs/design/<file>.md — § Section` (the design section being implemented)
  - **Acceptance-criteria checklist** copied from the sub-issue body, with each item ticked and a one-line note on how it is verified
  - Test results / smoke output (paste the relevant lines)
- Squash-merge to main; no merge commits in main
- PR > 400 lines: justify in the description or split
```

#### Edit G4: Add bug-tracking convention

**Location**: section "## Bug fix workflow" — append a new
subsection at the end of the section (around line 240).

**Existing text** (the existing exception note ends with):

```
**Exception**: bugs that cannot be tested in CI (e.g. flaky external API behavior). Document in `docs/known-issues.md` and add defensive code with a comment linking to the doc.
```

**Text to append after that paragraph**:

```markdown
### Bug as an independent issue

A bug is filed as its **own independent issue**, not as a sub-issue
of any task. The bug issue body includes:

- Provenance: `Found while implementing #<task-issue>` or
  `Regression in #<task-issue>` (link back to the task or epic where
  the bug originated, when known).
- Reproduction steps.
- The expected vs actual behavior.
- A reference to the failing test once it exists (per the protocol
  above).

The PR that fixes the bug uses `Closes #<bug-issue>` on its own line
in plain prose, the same auto-close phrasing rule as for tasks.

When labels are introduced, bug issues carry the `bug` label.
```

### Implementation order

The actual file edits land in one PR (`fix/17-governance-subissues`
or similar — but per H3 this is governance, so likely
`docs/17-governance-subissues`). All four governance edits + both
CLAUDE.md edits in one PR — they are tightly coupled (the CLAUDE.md
"Implementation-start protocol" references `gh issue view` of a task
issue that only exists under the new convention from governance.md).

### Cross-references after the change

Every existing v0.0.3 epic issue body still says "Tasks" with a
checkbox list. Those bodies stay as-is **for now**; they're updated
when the migration step (separate issue) batch-creates sub-issues and
re-renders epic bodies to point at them. The governance change does
not retroactively edit existing artifacts.

## Task breakdown

This change is small and tightly coupled — best landed in one PR
rather than split.

- [ ] **T17.1** — Apply edits C1, C2 to CLAUDE.md, edits G1–G4 to governance.md, per the exact text in this design doc. Verify markdown renders cleanly. (~30m)
- [ ] **T17.2** — End-to-end review of the rendered files; ensure no broken cross-references introduced. Manual smoke. (~15m)

(No sub-issue creation for T17.1/T17.2 since the governance change *itself* introduces sub-issues; bootstrapping uses checkboxes here.)

## Acceptance criteria

- [ ] CLAUDE.md contains the "Implementation-start protocol" section as specified in C1.
- [ ] CLAUDE.md workflow step 3's last bullet matches C2's replacement text exactly.
- [ ] governance.md lifecycle step 5 in the diagram matches G1's replacement text.
- [ ] governance.md contains the "Task tracking" section with the briefing template (G2) between "The Closed Loop Rule" and "Branch and commit conventions."
- [ ] governance.md "Pull Request rules" matches G3's replacement.
- [ ] governance.md "Bug fix workflow" ends with the "Bug as an independent issue" subsection (G4).
- [ ] Existing cross-references in CLAUDE.md and governance.md still resolve (no broken `[…](#…)` anchors introduced).
- [ ] Both files render cleanly on GitHub (manual check after PR is opened).

## Open questions

- **OPEN-17.1.** Where exactly within `docs/journal/<date>.md` and
  `docs/journal/README.md` should the new sub-issue convention be
  reflected? Likely just a one-line journal entry on the day the PR
  merges; the journal README format spec doesn't reference task
  tracking. **Resolution**: handle in the PR by appending to today's
  journal at merge time.
- **OPEN-17.2.** When labels are added (separate issue per OPEN-V4
  in the v0.0.3 vision), the bug-tracking section's "When labels are
  introduced, bug issues carry the `bug` label" hedges. Should this
  be tighter? **Resolution**: hedge stays. When the labels-issue
  lands, that issue's PR can edit governance.md to remove the
  hedge.
- **OPEN-17.3.** The briefing template's `Test plan` section is
  light. Does it need a "manual smoke required if applicable"
  reminder? **Resolution**: leave as-is for v0.0.3; observe how the
  first 3–5 sub-issues use it; tighten in a follow-up governance
  amendment if the field gets repeatedly under-filled.
