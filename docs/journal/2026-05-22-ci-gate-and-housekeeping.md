# 2026-05-22 — CI gate lands, issue tracker hits zero, README truth-up

> A long housekeeping session spanning 2026-05-21 evening → 05-22. It began
> from the previous arc's open follow-ups (#120 live trial, consolidate-memory,
> #104, CI gate) and kept going until the issue tracker was empty, the CI
> quality gate was live, the README was accurate + bilingual, and `main` was
> synced with `v1.0`.

## Session arc

Four user turns, each opening a front:

1. **"看还有什么工作，继续"** → closed #120 (S5 hook) + a consolidate-memory pass.
2. **"finish 104"** → uncovered a roadmap mis-citation; closed the smoke-script
   #104 **and** built the real CI gate (#122).
3. **"关 #2 / 同步 main / packages?"** → closed the dogfooding manifesto, synced
   v1.0→main (#123), and explained why the GitHub Packages tab is (correctly) empty.
4. **README** → accuracy review → fixes + 中文版 (#124/#125) → second main sync (#126).

## Done

### #120 — S5 git hook, closed
- Live trial in a fresh session: `git push --force` to a bogus remote was
  **blocked at the harness level** (deny) — git never executed. ask/allow
  classes confirmed by a direct script probe.
- Honest maturity call: marked `feedback_branch_workflow` **core-S4 + partial-S5
  backstop**, not full S5 — the hook only gates that rule's irreversible
  sub-ops, not its reversible core (feature-push / PR-to-main). Resisted
  over-claiming (same discipline as the previous arc).

### consolidate-memory — stale-anchor sweep (10 files)
- Killed the "permanent rule, transient anchor" anti-pattern: re-phrased
  hard-coded `v0.0.3` → `<dev-branch>` in 4 rule files + the index.
- Folded resolved decisions back in: #72 closed → `project_pure_worker_schemas`
  re-scoped to v1.0 Bucket 1; ADR-0013 D1 (no 5th writer role) →
  `project_writer_worker_gap` marked RESOLVED.
- Judgment: did **not** blanket-retrofit `S4` maturity tags (noise; easy to
  re-derive) — tag-on-change instead.

### #104 — fresh-install smoke script, closed
- The roadmap cited #104 as the CI gate; the **actual** #104 was the smoke
  script, already built in Epic 10 / T10.6. Surfaced the ambiguity instead of
  guessing → user chose to do both.
- Verified acceptance (idempotent / non-zero exit / per-step output) by
  inspection + `bash -n`; the only gap was a `docs/ops` pointer → added to
  `binary-build.md`.

### #122 — CI quality gate (the real Phase B), closed
- Full workflow: analyze → design doc (`docs/design/122-ci-quality-gate.md`) →
  issue → approval → implement.
- Project-specific design call: maestro's no-feature-PR workflow means a
  PR-only gate barely fires, so triggers are **push(`main`/`v*`) + pull_request**.
- Dogfooded: `coder` authored `ci.yml` + `pyproject.toml` edits, `reviewer` ×2;
  the 32 unused-imports went via `ruff --fix`, the 11 manual lint fixes inline.
  Ruleset = ruff default `E`+`F`, pinned `ruff==0.15.14`.
- **The gate caught real bugs on its first red run** (see moments).

### #2 — dogfooding manifesto, closed
- Exit condition (a release using workers for substantive code) satisfied since
  v0.0.3. Closed pointing at BUILD_LOG v0.0.3 + `docs/savings.md` + #122 itself
  (coder authored, reviewer passed).

### README — truth-up + 中文版 (#124/#125), closed
- Fixed: non-existent commands (`maestro logs`/`stats`), 3 dead doc links,
  `spec-writer`→`spec_writer`, an unshipped "Confidence escalation" gate that
  contradicted the status list, "Junior/Senior Engineer"→`coder`/`reviewer`,
  stale project status (v0.0.4 → "v0.1.0 latest / v1.0 dev"), deleted unfinished
  roadmap items + stale version numbers.
- Added `README.zh-CN.md` (translated from the **corrected** English) + language
  links both ways.
- H3 protected-doc flow: PR base `v1.0`, user review, merge — per the #121 precedent.

### main syncs (#123, #126)
- Two `v1.0`→`main` PRs (docs/CI only) — **no version bump, no tag**: baseline
  syncs, not releases (the binary build only fires on `v*.*.*` tags).
- Both also exercised the new gate's `pull_request` trigger green. `v1.0`
  retained as the dev branch throughout.

## Distinctive moments

### 1. The CI gate caught a real shipping bug on run #1
The first red CI run surfaced **`python-multipart` missing from runtime deps** —
`maestro webui`'s FastAPI form route imports it, so a clean `pip install maestro`
+ `maestro webui` would have **failed for end users**. The release smoke never
exercised webui forms, so this had shipped latent. The run also caught `httpx`
(dev/test), the bootstrap `mcp`/`openai` deps, and `DEEPSEEK_API_KEY`-read-at-import.
The gate became the clean-room that `feedback_clean_room_ci_verification`
prescribes — and the fixes were verified in a throwaway venv replicating CI, per
that rule. Same pattern as #120's fixture corpus and #104's smoke: **a new
defense layer pays for itself on first contact.**

### 2. "finish 104" was a trap the analysis caught
Taking "#104 = CI gate" at face value (it's what the roadmap *and* my own prior
summary said) would have built the wrong thing — or closed a half-done issue.
Reading the actual issue body revealed #104 was the smoke script (done) and the
CI gate was unfiled. Surfacing the fork instead of guessing was the whole game;
the roadmap mis-citation got corrected as a side effect.

### 3. Honesty over completeness when writing this journal
Writing the #122 section, I found its implementation commits (coder dispatch, 2
reviewer passes, two CI fixes, roadmap update) live in git + `dispatch-log.jsonl`
but sit **outside my visible conversation context** — that execution happened in
a stretch I couldn't replay turn-by-turn. Wrote the section from git + the
dispatch log as ground truth rather than reconstructing from memory. The standing
per-dispatch telemetry rule is exactly what made it recoverable.

## Numbers

| Metric | Value |
| --- | --- |
| Issues closed | 5 (#120, #104, #122, #2, #124) |
| Open issues remaining | **0** |
| PRs merged | 3 (#123 sync, #125 README→v1.0, #126 sync); #122's feature/fix branches were local merges to v1.0 |
| #122 worker dispatches | coder ×1 (2,877 tok / 62s) + reviewer ×2 (3,807 tok / 98s; 1,734 tok / 27s) |
| ruff violations cleaned | 43 (32 autofix + 11 manual) |
| Latent dep/env bugs caught by gate run #1 | 4 (python-multipart, httpx, bootstrap deps, DEEPSEEK_API_KEY) |
| Memory files consolidated | 10 |
| README change | EN ~33 lines touched; ZH +304 new (`README.zh-CN.md`) |
| main syncs | 2 (no tags, no version bump) |
| Test suite | 568 passed / 2 skipped — green throughout |

## Lessons learned (carry-forward)

1. **A defense layer earns its keep on first contact.** CI gate → a real
   shipping bug (`python-multipart`) on run #1. Don't defer the gate "until the
   code is clean"; the gate is how you find out it isn't.
2. **CI is the clean-room, institutionalized.** `feedback_clean_room_ci_verification`
   was about manual pre-push checks; the gate makes it automatic. "Passes locally"
   dep/env gaps are precisely what it surfaces.
3. **The issue body beats a secondary citation.** When the roadmap and the issue
   disagree on what #104 is, trust the issue and reconcile the roadmap.
4. **Write journals from ground truth, not memory.** git + dispatch-log are the
   record when context is partial.

## Open follow-ups

- **`python-multipart` was a real latent shipping gap.** Worth considering whether
  the fresh-install smoke should exercise `maestro webui` (forms), not just the
  MCP handshake — so the next such gap is caught pre-release, not by CI after.
- v1.0 roadmap Bucket items still open: scribe schema rework (`#72` area /
  `content_type`), `known-issues.md` audit, reviewer-payload contract-sheet
  default, macOS signing, Windows/Linux real-machine install tests, user manual.
- `main` now carries the CI gate, so pushes/PRs to `main` are gated too.

## What's next

Issue tracker is at zero and `main == v1.0`. Clean checkpoint. The next
substantive work is a v1.0 roadmap Bucket item — highest-leverage is probably the
scribe `content_type` rework (it unblocks the MCP schema freeze) or making the
reviewer-payload contract-sheet the default.
