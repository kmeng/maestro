# 2026-05-19 — Memory drift, rule lifecycle, and the S5 hook (arc 2)

> Second arc of the day. The first (`2026-05-19-v1.0-scoping.md`) ended
> with the v1.0 milestone + roadmap landed. This arc started when the
> user looked at remote and saw it was messy — and the question
> "why drift despite memory?" turned into a full reflection on the
> memory architecture, a rule-maturity lifecycle framework, and a
> three-layer defense implementation (memory rewrite + CLAUDE.md
> session-start check + a working PreToolUse git hook).

## Session arc

Trigger: after the v1.0 docs work merged, the user noticed 3 stale
`docs/*` branches on remote and no `v1.0` dev branch — "感觉状态乱掉了".
The drift: this session I'd pushed `docs/N-slug` branches to remote and
PR'd each directly to `main`, instead of routing through a dev branch;
and I never created the post-v0.1.0 dev branch.

The user's real question wasn't "clean it up" — it was **"these
decisions are already in memory, why did drift still happen, and how do
we solve it thoroughly?"** That reframed the whole arc from cleanup to
mechanism.

The arc then walked: memory-architecture analysis → rule-maturity
lifecycle framework → implementing the defenses we'd just designed.

## Done

### Cleanup (the immediate mess)
- Deleted 3 stale remote branches (`docs/114-*`, `docs/116-*`,
  `docs/journal-2026-05-19`).
- Created + pushed `v1.0` dev branch from `main`. Remote now clean:
  `main` + `v0.0.3` + `v0.0.4` + `v1.0`.
- Decided NOT to roll back today's docs commits on `main` (planning
  docs, no product behavior; rollback cost > formal-correctness value).

### Memory layer (S2→S4 fixes, out of repo)
- **Rewrote `feedback_branch_workflow`**: abstracted the anchor
  (`v0.0.3` → `<dev-branch>` role), added a maturity tag, added
  "anchor-expiry handling" (a stale version number does not retire the
  rule), added the **release-transition rule** (ship day → create next
  dev branch), recorded the 2026-05-19 violation.
- Updated `MEMORY.md` index line to match.
- Cross-referenced the new hook in `feedback_github_approval`.

### Three-layer defense (the structural solution)
- **CLAUDE.md (#119 → PR #121)**: added session-start protocol step 4
  — verify a current dev branch exists on remote; surface the gap if
  `main` is last-shipped and no next dev branch exists. PR base = `v1.0`
  (dogfooding the corrected workflow); merged after user review; #119
  closed manually (PR base ≠ default branch, so `Closes` didn't fire).
- **S5 git hook (#120)**: design doc `docs/design/120-s5-git-hooks.md`
  (merged to v1.0) + `~/.claude/hooks/guard-irreversible-git.sh`. Gates
  force-push & `gh issue|pr delete` (`deny`); remote-branch-delete,
  `branch -D`, `reset --hard`, non-temp `rm -rf` (`ask`). Validated:
  **28/28 fixtures + 4/4 fail-open**. Wired into `~/.claude/settings.json`.

### Obsidian (methodology, authored by orchestrator per ADR-0013 D1)
- `CODE-2026-05-19-001.md` — v1.0 scoping / "4 roles beats 7" (arc 1).
- `CODE-2026-05-19-002.md` — "记下来 ≠ 不漂移" / rule-maturity pipeline
  (this arc).

## Distinctive moments

### 1. The anti-pattern: permanent rule, transient anchor

The rule "feature 不推 remote，merge 到 v0.0.3" had a **permanent
invariant** (feature local; merge to current dev branch) anchored on a
**transient instance** (`v0.0.3`, which had since closed). When the
anchor expired, the index line looked outdated and I — cold-starting —
silently retired the whole rule. The rule didn't die of wrong content;
it died of an expired anchor. Fix: phrase permanent rules against
stable roles (`<dev-branch>`), never specific instances; add explicit
"if the version number is closed, don't retire the rule."

### 2. The rule-maturity lifecycle (S0–S5)

The user named the real structure: rules evolve temporary → permanent,
and controlling the rhythm matters. Mapped it to a 5-stage pipeline
isomorphic to the project's worker shadow→promoted model:

- S0 observation → S1 hypothesis → S2 working rule (in-session) →
  S3 candidate memory (provisional) → S4 established memory →
  S5 enforced invariant (hook).

Each transition has a natural ritual trigger: journal = S2→S3,
consolidate-memory = S3→S4, **incident = S4→S5**. Key insight:
"a rule that's in memory yet still got violated" is itself the S4→S5
promotion trigger — don't respond with "I'll remember next time"
(useless for a cold-start agent), respond by upgrading the defense layer.

### 3. Honesty catch — didn't over-claim S5

While tagging `feedback_branch_workflow` as S5, I caught that the hook
does **not** actually cover that rule's core scenario (pushing a feature
branch to remote, PR-ing to main) — because those are *reversible* and
intentionally excluded from deny/ask. The hook gates *irreversible* ops.
So I marked it honestly: the hook is a *partial* backstop; the primary
defense for branch-workflow remains the session-start check (#119) +
active recall. Resisted the temptation to claim full S5 coverage.

### 4. Dogfooded the corrected workflow, same day as fixing it

- Design doc (#120): feature branch → local merge to `v1.0` → push →
  delete local branch. No remote feature branch, no PR. The correct path.
- CLAUDE.md (#119, H3): the exception — H3 needs a PR, so PR to `v1.0`
  (not `main`), left for review, not auto-merged.
- Merge cleanup: used `gh pr merge --delete-branch` to delete the remote
  branch automatically — exactly the step I'd missed earlier today.

### 5. A real bug in the hook, caught by fixtures

First fixture run: `git push --force origin main` slipped through as
allow while `-f` was correctly denied. Root cause: my `has()` helper
used only `$1`, but I called `has -- 'pattern'` at two sites — the `--`
became `$1`, so the negated force-with-lease check actually grepped for
`--`, matching any command containing `--` and skipping the whole
force-push block. Fix: `grep -Eq -e "$1"` + drop the stray `--`.
The fixture corpus (28 cases) caught a bug that would have shipped a
guard with a hole exactly where it mattered most (force-push to main).

## Numbers (arc 2)

| Metric | Value |
| --- | --- |
| Stale remote branches deleted | 3 |
| Dev branches created | 1 (`v1.0`) |
| Memory files edited | 3 (`feedback_branch_workflow`, `MEMORY.md`, `feedback_github_approval`) |
| Issues opened | 2 (#119, #120) |
| Issues closed | 1 (#119) |
| PRs merged | 1 (#121, base `v1.0`) |
| Design docs | 1 (#120) |
| Hook fixtures | 28/28 + 4/4 fail-open |
| Obsidian articles | 2 (001 arc1, 002 arc2) |
| Worker dispatches | 1 (claude-code-guide — hook API verification) |
| Lines of code written | ~70 (hook script, environment-local, not repo-tracked) |

## Lessons learned (carry-forward)

1. **Permanent rule, transient anchor** is a named anti-pattern now.
   Phrase long-lived rules against stable roles; add anchor-expiry
   handling so a dead instance never silently retires the rule.
2. **"Violated despite being in memory" is the S4→S5 trigger.** Convert
   the violation into structure (hook / session-start check), not into
   a "remember harder" promise.
3. **Defense strength = violation-cost × irreversibility.** Reversible
   drift (branch routing) → memory + session-start check is enough.
   Irreversible drift (force-push, deletes) → deterministic hook.
4. **Hooks load at session start.** A settings.json change is not live
   in the authoring session — it takes effect next session. Don't claim
   live coverage without a fresh-session trial.
5. **PR base ≠ default branch → `Closes #N` does not auto-fire.** When a
   PR targets a dev branch, close the linked issue manually.
6. **A fixture corpus pays for itself immediately.** 28 cases caught a
   real hole in the guard before it went live.

## Open follow-ups

- **#120 live trial** — next session, confirm the hook fires on a gated
  op (a benign `ask`-class command, NOT a real force-push).
- **consolidate-memory pass** — other `v0.0.3` stale anchors remain
  (e.g. `feedback_auto_execute_mechanical_actions` index line). Same
  anti-pattern; sweep them in the next S3→S4 ritual + retrofit the
  maturity-tag convention across memories.
- **#104 Phase B CI gate**, plus the v1.0 roadmap bucket items
  (reviewer-payload contract-sheet adoption is the highest-leverage one).

## What's next

Session ending on user's signal ("今天结束，写journal"). Two things
self-activate next session without anyone remembering:
1. The git hook goes live (settings.json loaded fresh).
2. The session-start branch-state check runs (now in CLAUDE.md on
   `v1.0`).

The chain from this arc — drift discovered → diagnosed → methodology
distilled → three-layer defense shipped — is closed.
