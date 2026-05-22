# Maestro v1.0 roadmap

**Status**: draft
**Date**: 2026-05-19
**Issue**: #116
**Milestone**: [v1.0](https://github.com/kmeng/maestro/milestone/1)
**Authored by**: orchestrator + user (per [ADR-0013](adr/0013-worker-roster-policy-for-1.0.md) — judgment-dense roadmapping stays at the highest capability tier)

v1.0 is the first release that claims durability — schema stable, bug
debt drained, download-to-use loop complete on all three platforms.
This document is the criteria-driven scope-of-record. It is updated
whenever an item moves status; closure of all bucket items plus green
acceptance criteria equals the v1.0 tag.

## Acceptance criteria

A release is v1.0 only when **all three** hold:

1. **No feature gap** — every shipped role / tool / surface either
   reached promoted status with measured quality, or was explicitly
   retired with a recorded reason
2. **No bug debt** — CI quality gate green; `docs/known-issues.md`
   exists and is empty (or contains only intentionally-deferred items
   with documented mitigations)
3. **Download-to-use loop closed** — a non-developer on macOS / Linux
   / Windows can download → install → use Maestro inside Claude Code
   without developer-assisted intervention

The three buckets below decompose these criteria into work items.
Items get their own GitHub issue under the v1.0 milestone when work
starts — this roadmap intentionally does not pre-create placeholder
issues to avoid issue-tracker noise.

## Bucket 1 — No feature gap

| Item | Status | Notes |
| --- | --- | --- |
| `spec_writer` shadow → decision | shadow | Per ADR-0013 D2: stays shadow through 1.0. Decision recorded — no trial wave needed |
| `verifier` shadow → trial wave → promote-or-retire | shadow, 1 dispatch on record | Needs a real task host; pick low-risk canary in 1.0 window |
| `scribe` schema rework (workflow-agnostic + `content_type`) | not started | Covers #72 + ADR-0013 D1 (`journal_entry` / `build_log_section` / `troubleshooting_entry` content types) |
| Epic 7 close status verification (web UI savings) | unknown | Verify per-time + per-role coverage matches Epic 7 acceptance |
| MCP tool schema stability + semver commitment | not started | After scribe rework lands, freeze + document the surface |

## Bucket 2 — No bug debt

| Item | Status | Notes |
| --- | --- | --- |
| Phase B CI quality gate (ruff + pytest on push/PR) | ✅ done (#122, 2026-05-22) | Green on v1.0. Caught 3 latent issues on first run (undeclared `python-multipart`/`httpx`, non-hermetic API key). (NB: #104 was the fresh-install smoke script — done — not this; earlier drafts mis-cited it here.) |
| `docs/known-issues.md` creation + audit | not started | Governance referenced it; file doesn't exist |
| CI actions Node 20 deprecation upgrade | identified | Pre-2026-06 deadline; non-blocking until then |
| Reviewer-payload contract-sheet adoption (cost lever) | partial since T8.4 | Per ADR-0013 D3: make default; document playbook; update memory `feedback_worker_payload_completeness` |

## Bucket 3 — Download-to-use loop closed

| Item | Status | Notes |
| --- | --- | --- |
| macOS code-signing + notarization | not started | Removes Gatekeeper first-run friction |
| Windows SmartScreen handling | not started | Either code-sign or document workaround |
| Linux real-machine non-developer install test | only CI smoke | Bare Ubuntu / Fedora VM, non-dev follows README only |
| Windows real-machine non-developer install test | only CI smoke | Bare Win11 VM, non-dev follows README only |
| Upgrade path documentation | not started | Until in-app updater exists, document "download new + maestro install" |
| Troubleshooting docs | not started | Common failures: Claude Code doesn't see MCP / restart missed / install path issues |
| User manual (operational sections) | not started | Per ADR-0013 D1: orchestrator + user authors "what to say"; scribe renders "how to do it" |

## Out of scope for v1.0 (parked for v1.x+)

| Item | Reason parked |
| --- | --- |
| `spec_writer` promotion | ADR-0013 D2 — saving doesn't clear complexity tax |
| Homebrew tap / cask | v1.x — needs name + audience first |
| In-app auto-updater (PyApp / self-update feed) | v1.x — significant scope; upgrade docs are the v1.0 substitute |
| 5th "writer" / "author" role | ADR-0013 D1 — extending `scribe` covers the residual surface |
| MCP schema breaking changes | Post-v1.0 stability commitment forbids them |

## Cadence + process

- Each bucket item gets its own GitHub issue under the v1.0 milestone
  before work starts
- Items follow the standard `analyze → design → implementation-start`
  workflow per [CLAUDE.md](../CLAUDE.md)
- The acceptance criteria above are the only v1.0 ship checklist —
  no separate punch list
- This roadmap is updated whenever an item moves status
