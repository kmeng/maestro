# ADR-0010: Dispatch log format + effectiveness methodology

**Status**: accepted
**Date**: 2026-05-10
**Issue**: #61 (parent epic #56)
**Related**:
[`docs/savings-methodology.md`](../savings-methodology.md),
[`docs/design/56-effectiveness-page.md`](../design/56-effectiveness-page.md)

## Context

Epic 6 produces a public effectiveness page
([`docs/savings.md`](../savings.md)) that backs the project's
"near-flagship code at 10–20% of the cost" claim with mechanical
evidence. Three load-bearing format/methodology decisions were
made during design and consolidated here so they can be cited
without re-reading the full design doc.

## Decision

### D1. Storage format: append-only JSONL

`docs/data/dispatch-log.jsonl` is the audit trail. One row per
dispatch, written by `_emit_dispatch_row()` in
`bootstrap/maestro_server.py`. Schema is versioned (`schema_version`
field, currently 1) and documented at design 56 § 2.1.

Rows are append-only and never rewritten. Corrections (e.g.,
re-attributing a row to a different task) take the form of a new
row referencing the original via `supersedes`. The renderer
honours `supersedes` chains.

The file is committed to git (gitignore exception added in this
task; see `.gitignore`). Any reader who clones the repo can
reproduce the rendered page byte-for-byte.

### D2. Opus baseline = same-token rate substitution

For each measured dispatch row, the renderer computes
`opus_$ = (prompt × opus_input_rate + completion × opus_output_rate)
/ 1M`. The saved figure is `opus_$ − worker_$`.

This is **not** a claim that Opus would use the same tokens for
the same task. Empirically Opus usually uses *more* tokens on
non-trivial tasks (longer reasoning, more candidates), so the
real saving would be *higher* than reported. Reporting a
same-token substitution therefore yields a saving that is at
least the reported one and never more flattering than reality.

The decision to use a substitution at all (rather than skip the
saving claim entirely) is bounded by the value of having a
publicly-defensible number. The number's interpretation is
documented at length in
[`docs/savings-methodology.md`](../savings-methodology.md) § 3, so
the public claim and its limits travel together.

### D3. Provider rates baked into renderer code

The rate table lives as a versioned constant
(`PROVIDER_RATES_USD_PER_M_TOKENS`) inside
[`scripts/render_savings.py`](../../scripts/render_savings.py).
Updates require an explicit code change (and PR); silent rate
drift is impossible. Snapshot date is in a code comment.

This means a historical commit re-renders to the same numbers it
was committed with, even if external rates change. Combined with
D1 (committed JSONL), historical pages are fully reproducible
from any commit.

## Alternatives considered

- **Per-task JSON files** (one file per closed task) instead of
  one append-only JSONL. Rejected: scattered state, harder to
  aggregate, no clear advantage. JSONL is line-atomic on POSIX
  for our row sizes (<500 bytes), so concurrency concerns are
  also satisfied.

- **SQLite database**. Rejected for v0.0.3: introduces a binary
  artefact in git (poor diff), needs migration tooling for
  schema changes, and the audit-trail use case wants
  human-readable + grep-able more than it wants relational
  queries. Revisit if aggregations get expensive (>10k rows).

- **Live Opus instrumentation** (run the same task on Opus to
  measure real Opus cost). Rejected: doubles every dispatch
  cost, defeats the point. Also unlikely to be representative
  on a one-shot basis (variance per dispatch is large).

- **Skip the saving claim entirely; only report worker spend**.
  Rejected: the project's whole pitch is the saving — refusing
  to quantify it because the comparison is imperfect would be
  worse than quantifying it with stated limits. The methodology
  page exists precisely to make the comparison's limits legible.

- **Provider rates loaded from a config file** (e.g., YAML or
  JSON in `docs/data/`). Rejected: invites silent drift if the
  file is edited without re-rendering all historical pages, and
  introduces config-loading code for a 5-line constant. Baking
  into renderer code with a snapshot-date comment is simpler and
  makes drift visible in `git log`.

## Consequences

### Good

- Public claim is reproducible from any commit. `git checkout
  <hash> && python scripts/render_savings.py` produces what the
  page said at that point in time.
- The "✓ measured / ⚠ estimated" distinction (renderer behaviour;
  see methodology § 8) lets the page age without retraction —
  estimates can be replaced by measurements without rewriting
  history.
- Schema is versioned (`schema_version: 1`); a future change
  (e.g., split prompt-cache hit/miss tokens) bumps the version
  and the renderer can branch on it.

### Bad / risks

- **Repo-size growth**. JSONL rows are small (~400 bytes); even
  at 10k dispatches this is ~4MB. Not a concern at v0.0.x scale,
  but worth a watchpoint at large org adoption.
- **Privacy**. The committed JSONL exposes every worker dispatch:
  model name, token counts, wall time, task ID. If maestro
  installs in a private project, the user should set
  `MAESTRO_DISPATCH_LOG=""` (telemetry disabled) or redirect to
  a path outside the repo. Documented in methodology § 7.
- **Stale rates if PR review is slow**. The bake-in design
  trades silent drift for explicit drift; a rate change still
  requires somebody to notice and PR. Mitigation: an issue per
  rate update is sufficient at our scale.
- **Saving number's "lower bound" framing requires the reader to
  understand what was substituted**. Mitigated by methodology
  § 3 making the substitution and its conservatism explicit.

### Reversibility

**High** for D1 and D3 (data format / code constants are mechanical
to migrate). **Medium** for D2: changing the baseline formula
would invalidate historical comparisons unless old pages stay
pinned to the original formula. Practically, formula changes
should bump `schema_version` and the renderer should branch.

## Sibling open questions resolved

- Design 56 D4 (storage format) — formalised here.
- Design 56 D1 (Opus baseline conservatism) — formalised here.
- Design 56 § 4.3 (rates baked-in) — formalised here.

## Open questions deferred

- CI enforcement of "render is byte-for-byte stable" — deferred
  to v0.0.4 per design 56 D9.
- Per-version aggregate (savings per release) — out of scope per
  design 56 D2; trivially addable later if useful.
