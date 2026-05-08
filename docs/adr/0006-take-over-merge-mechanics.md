# ADR-0006: Take-over flow — merge mechanics

**Status**: accepted
**Date**: 2026-05-08
**Issue**: #14

## Context

[ADR-0005](0005-scaffolding-template-set.md) settled what files
Maestro's scaffolding writes into a user's project. This ADR settles
*how* each write happens — the operation taxonomy, idempotence rules,
atomicity guarantees, and pre-flight checks that make the additive /
scoped / idempotent guarantees concrete.

The constraints are sharp:

- **Additive.** Maestro must never overwrite user content. A user's
  hand-edited file is sacred unless they explicitly confirm a write.
- **Idempotent.** Re-running take-over on the same project produces no
  changes. The user can hit "apply" twice without a different second
  outcome.
- **Scoped.** The scaffolding engine touches only the files in
  ADR-0005's two sets — never wanders.
- **Conflicts surface, never auto-resolve.** Whenever in doubt, the
  user decides.

## Decision

### Operation taxonomy

The scaffolding engine processes a list of file operations. Each
candidate file resolves to exactly one operation type per take-over
run:

| Op | Trigger | Effect |
|---|---|---|
| `CREATE` | Destination doesn't exist | Atomic write-then-rename of the rendered template |
| `APPEND_DELIMITED` | Destination exists, contains no Maestro-delimited section, file is mergeable (CLAUDE.md is the only such file in v0.0.3) | Atomic write of `existing + "\n\n" + delimited_section` to a temp file, then `os.replace` |
| `NOOP` | Destination already matches the would-be result (exact bytes for replacement files; current-version delimited section for mergeable files) | Nothing |
| `CONFLICT` | Any other case | Surface to the user; never auto-resolve |

Plan generation walks the file list once and produces an ordered list
of `(file, op, detail)` tuples. The plan is presented to the user
through Epic 2's plan-preview UX (D3) before any write.

### Idempotence rules

#### Pure-replacement files

`.maestro/.gitignore`, `.gitignore`, `README.md`.

Idempotence by **exact-bytes match**:

- Read existing file → compare byte-for-byte to the rendered template.
- Equal → `NOOP`.
- File absent → `CREATE`.
- Different and the file is in the take-over set (`.maestro/.gitignore`)
  → `CONFLICT`. (User has a custom version; Maestro doesn't replace it.)
- Different and the file is in the new-project-only set (`.gitignore`,
  `README.md`) → never reached. New-project flow runs only on empty /
  non-existent directories, so existence-with-divergence cannot happen.

#### Mergeable files (CLAUDE.md)

Idempotence by **delimiter scan** of the existing file content:

- Search for blocks bounded by `<!-- maestro:start v=N -->` and
  `<!-- maestro:end v=N -->` (matching `N` on both ends).
- Found `v=1` block, body matches current template body byte-for-byte
  → `NOOP`.
- Found `v=1` block, body matches **after stripping leading and
  trailing whitespace** → `NOOP`. Tolerates the user adding blank
  lines around the section.
- Found `v=1` block, body differs → `CONFLICT` (user has hand-edited
  the Maestro section).
- Found `v=N` where `N != 1` → `CONFLICT` (older or unknown Maestro
  version; v0.0.3 does not auto-migrate).
- Found multiple `<!-- maestro:start … -->` markers → `CONFLICT`
  (corrupt; surfacing instead of guessing).
- Found `maestro:start` without a matching `maestro:end` → `CONFLICT`.
- No marker, file exists → `APPEND_DELIMITED`.
- File absent → `CREATE`.

The delimiter scan is a substring / regex pass, not a markdown parse.
It looks for *our* exact delimiters; it does not interpret arbitrary
markdown structure.

### Atomicity

**Per-file atomic, not transactional across files.**

Each individual file write uses `write-then-rename` (`os.replace`):

1. Write the new content to a temp file in the same directory.
2. `os.replace(temp, dest)` — POSIX-atomic rename on the same
   filesystem.

A concurrent reader (e.g., Maestro's MCP server reading `team.yaml`
during the wizard's save — same mechanic from Epic 1 D4) sees either
the old file or the new one, never a torn intermediate.

The engine does **not** transactionally apply all-or-nothing across
multiple files:

- A truly transactional cross-file apply requires a journal / staging
  area / rollback path. Disproportionate for v0.0.3's tiny file lists
  (4 max for new-project, 2 max for take-over).
- The blast radius of partial apply is bounded. If file 1 succeeds
  and file 2 fails, the user sees the partial state plus the specific
  error and re-runs. Idempotence makes the re-run safe.
- Failure modes stay legible: each write either succeeds atomically
  or fails with a known error. No silent half-states.

### Pre-flight checks (run before any plan can be applied)

The engine refuses to apply a plan unless these pass:

1. **Project root resolves.** The path the user pointed at exists and
   is a directory.
2. **Git state matches the flow.** Take-over: the directory must be
   a git repo (`.git/` present). New-project: the directory must be
   empty or non-existent (Maestro will `git init`).
3. **No uncommitted changes (take-over only).** If `git status
   --porcelain` shows changes, the apply is refused with a clear
   message asking the user to commit, stash, or explicitly confirm.
   Default-refuse so we never write atop an in-progress edit.
4. **No unexpected `.maestro/` directory (take-over only).** If
   `.maestro/` exists with content beyond what take-over would
   produce (e.g., `team.yaml` is already there from a previous
   take-over), the engine flags `CONFLICT` per relevant file and
   surfaces the situation through the plan preview rather than
   silently overwriting or skipping.

Pre-flight failures are surfaced to the user through Epic 2's
plan-preview UX (D3) the same way per-file `CONFLICT` rows are.

### What the engine deliberately does not do

- **No in-place rewriting.** Every write is full-file content
  replacement. Mergeable files (CLAUDE.md) read existing content into
  memory, splice in the delimited section, and write the whole result
  back atomically. No streaming partial edits.
- **No backup files.** Maestro never leaves `CLAUDE.md.bak` or similar
  artifacts. The pre-flight uncommitted-changes check ensures git
  has the prior version; relying on git is cleaner than scattering
  `.bak` files.
- **No auto-resolution of conflicts.** Every `CONFLICT` is the user's
  decision. The engine surfaces what differs; the user chooses.
- **Line endings.** Write `\n` (LF). Read tolerantly — accept `\r\n`
  files on input by normalizing to LF for comparison. Output is always
  LF. Compatible with git's default `core.autocrlf` behavior.

## Alternatives considered

- **Transactional cross-file apply** (all-or-nothing). Rejected.
  Requires a journal / staging area; disproportionate for the tiny
  file lists. The per-file atomic guarantee plus idempotent re-run is
  sufficient.
- **Auto-resolve simple conflicts** (e.g., older Maestro section
  version → upgrade). Rejected for v0.0.3. The first time we
  auto-migrate something, we want explicit user awareness because the
  change is by definition something Maestro decided. v0.0.3 ships v=1
  only; auto-migration design lands when the first content-changing
  Maestro release is on the table (deferred per OPEN-2.4).
- **Backup files (`CLAUDE.md.bak`).** Rejected. Backup files are
  clutter the user has to manage. The git uncommitted-changes
  pre-flight makes git itself the backup mechanism — much cleaner.
- **In-place section rewriting** (rewrite *just* the delimited block,
  keeping the rest of the file unchanged at byte level). Tempting,
  but read-modify-write of the whole file is simpler and the file
  sizes are tiny. The temp-file-then-rename pattern stays the same
  shape regardless. Rejected for not being worth the complexity.
- **Markdown-aware merge** (parse the existing CLAUDE.md, treat the
  Maestro section as a tree node). Rejected. Markdown parsers vary;
  every choice introduces interpretation surprises. Plain delimiter
  scan over file content is unambiguous and easy to test. The
  delimiter format is tied to ADR-0005's reversibility note —
  changing the format requires migration code, but the scan logic
  itself is trivial.
- **Tolerate body whitespace differences anywhere inside the
  delimited section** (not just leading/trailing). Rejected as
  imprecise — we'd be papering over real edits the user might have
  made. Trim leading/trailing only; treat any other whitespace
  difference as `CONFLICT`.

## Consequences

### Good

- **Operation taxonomy makes "what happens to each file" predictable.**
  Plan generation produces a finite, enumerable result the UX can
  render straightforwardly.
- **Idempotence is well-defined per file type** — no fuzzy "we think
  it matches" cases. Either bytes match (replacement files) or the
  delimiter block matches (mergeable files).
- **Per-file atomicity is achievable with `os.replace`** — no journal,
  no rollback bookkeeping. Simple to implement, simple to reason
  about.
- **Pre-flight checks catch the dangerous cases early** — uncommitted
  changes, missing git repo, unexpected `.maestro/` content. The user
  hears about problems before any write happens.
- **Engine never auto-resolves** means user-trust scales: there is no
  surprising-thing-Maestro-did-on-its-own. Every change is consented
  to in the plan preview.

### Bad / risks

- **Per-file atomicity allows partial state.** A `CLAUDE.md` write
  succeeds but the subsequent `.maestro/.gitignore` fails. The user
  sees a half-applied take-over. Mitigation: idempotent re-run is
  safe; partial state is bounded and legible.
- **Whitespace tolerance is one-sided.** A user who reformats the
  Maestro section internally hits `CONFLICT` rather than `NOOP`. By
  design — but reports may surface that this is too strict.
  Mitigation: documented; the exact-section-body discipline keeps
  Maestro from silently accepting edits that diverge from the
  intended template.
- **The delimiter format is now load-bearing.** Once user projects
  have `<!-- maestro:start v=1 -->`, changing the syntax requires
  migration code. ADR-0005 already flagged this; this ADR depends on
  it.
- **No auto-migration of `v=N` sections** means each Maestro release
  that changes the section content needs explicit migration logic —
  more design work later. Mitigation: cost is paid only when content
  actually changes; v0.0.3 ships v=1 only.
- **Pre-flight uncommitted-changes check refuses on dirty trees.**
  Some users may want to take-over their own in-progress edits and
  feel the refusal is paternalistic. Mitigation: the message says
  how to proceed (commit, stash, or explicit confirm). The default
  is conservative; the user has agency.

### Reversibility

- **Operation taxonomy: easy to extend.** Adding a fifth operation
  type (e.g., `MIGRATE_SECTION` for v=1 → v=2) is additive. Existing
  ops keep their meanings.
- **Idempotence rules: medium.** Tightening (e.g., dropping
  whitespace tolerance) breaks installs that relied on the
  tolerance. Loosening is safe.
- **Atomicity decision: easy to upgrade.** Moving from per-file
  atomicity to transactional apply is implementable later as an
  optional path; existing per-file behavior keeps working.
- **Pre-flight checks: easy to add or remove.** Each check is
  independent.
