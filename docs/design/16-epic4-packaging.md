# Design: Epic 4 — packaging and distribution (placeholder, deferred)

**Issue**: #16
**Status**: draft (deferred — placeholder only)

> **This document is a placeholder.** Epic 4 is deferred from v0.0.3
> implementation. This file exists so the v0.0.3 product vision has all
> five epics represented in `docs/design/`, and so early constraints
> surfaced by Epics 0–3 have a place to land.
>
> Detailed design happens post-v0.0.3, in its own pass-1 → pass-2 cycle.

## Problem

For Maestro to reach end users, it must ship as something other than
"git clone + pip install". An end user — non-developer or
developer-not-here-to-debug-Python — needs to install Maestro and start
the Web UI without touching a terminal beyond a launch command, ideally
not at all.

Epic 4 covers:

- Packaging Maestro as a single distributable (single binary, installer
  script, or platform-specific app bundle — choice deferred).
- A launcher that starts the Web UI process (and, where applicable,
  arranges for Claude Code to find the MCP server).
- Update mechanism (or explicit non-mechanism — "download the new
  version").

## Out of scope (this round)

This entire epic is out of scope for v0.0.3 implementation. v0.0.3 ships
as `git clone + run` with manual Web UI launch. Early adopters and
contributors are the audience for v0.0.3.

## Functional design

Deferred to Epic 4's own pass-1 design round, post-v0.0.3.

## Technical design

Deferred to Epic 4's own pass-1 design round, post-v0.0.3.

## Task breakdown

Deferred. No tasks scheduled for v0.0.3.

## Acceptance criteria

Deferred. No v0.0.3 acceptance criteria for this epic.

## Open questions

These are constraints from Epics 0–3 that Epic 4 will inherit. Captured
here so they are not lost between releases.

- **OPEN-4.1.** Two-process model (Web UI long-lived, MCP server stdio
  subprocess of Claude Code) means the launcher has two responsibilities:
  (a) start the Web UI process when the user opens Maestro; (b) ensure
  Claude Code's MCP-server configuration points at the right Python
  entry point. The second is non-trivial when Maestro is packaged as an
  opaque binary — Claude Code expects a command it can spawn as a stdio
  subprocess.
- **OPEN-4.2.** Port-conflict strategy chosen in Epic 0 (OPEN-0.3) affects
  the launcher: if the preferred port is taken and the fallback is
  "pick another port," the launcher must communicate the chosen port to
  the user (browser auto-open URL, terminal print, system notification?).
- **OPEN-4.3.** Update model. Two camps: (a) Maestro auto-updates (more
  work, more failure modes, but better UX for non-developers); (b) the
  user downloads a new release (simpler, fits open-source distribution
  norms). Pass-1-of-Epic-4 decision.
- **OPEN-4.4.** Distribution channels. PyPI? Homebrew? GitHub Releases
  binaries? Single platform-native installers? All of the above is the
  default-yes answer; the actual prioritization happens in Epic 4's own
  design round.
- **OPEN-4.5.** Trigger to promote Epic 4 into v0.0.3 scope. If Epics
  0–3 prove unusable without packaging — e.g., the manual Web UI launch
  is so painful that early adopters abandon it — packaging gets pulled
  forward. Until then, deferred.
