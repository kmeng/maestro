# Epic 7 manual checklist — Web UI savings page

The automated half lives in [`epic7_smoke.sh`](epic7_smoke.sh) and covers
the 4 state transitions + HTML-string assertions. This manual half
covers the things only a human-in-the-browser can judge: visual
hierarchy, copy quality, number-vs-truth correspondence against the
committed `docs/savings.md`, link targets, and dev-tools console health.

Run after `epic7_smoke.sh` passes. Anything that fails here → file a
follow-up issue. **Do not silently fix during smoke.**

## Setup

```bash
# Boot the launcher against the real project JSONL (env unset).
cd <repo-root>
maestro-webui
# Open http://127.0.0.1:19830/savings in a browser.
```

## §1 Happy state — real project data

Prereq: `docs/data/dispatch-log.jsonl` exists and `docs/savings.md` is
current (run `python scripts/render_savings.py` first if unsure).

- [ ] **Title strip** reads `Dispatch Savings` (h1).
- [ ] **Headline sentence** matches the committed `docs/savings.md`
      headline numbers:
  - same dispatch count
  - same total tokens (formatted with thousands separator)
  - same saved $ amount (2 decimal places)
  - same saved % (1 decimal place)
- [ ] **Per-role table** has exactly these columns in this order:
      `Role | Dispatches | Total tokens | Avg tokens/call | Avg wall (s) | Worker $ | Est. Opus $`.
- [ ] Per-role row counts match `docs/savings.md` per-role section.
- [ ] **Per-time table** has exactly these columns in this order:
      `Date | Dispatches | Tokens | Worker $ | Est. Opus $ | Saved`.
- [ ] Per-time rows are reverse-chronological (newest UTC day first).
- [ ] Dates are `YYYY-MM-DD` (no time component).
- [ ] **Footer**:
  - [ ] `Reading from: <code>...</code>` shows the absolute project
        JSONL path.
  - [ ] `Last dispatch: <ISO Z timestamp>` matches
        `git log -1 --format=%cI docs/data/dispatch-log.jsonl`-era
        latest started_at value.
  - [ ] `Telemetry: enabled · how to disable` link.
- [ ] **Methodology link** target: clicking `how to disable`
      attempts to navigate to `/docs/savings-methodology.md#7-disabling-telemetry`.
      (The link may 404 in the dev server — that's expected; this
      checklist verifies the *href*, not the target's existence.)

## §2 Empty state

```bash
MAESTRO_DISPATCH_LOG=/tmp/no-such-file.jsonl maestro-webui
# Open http://127.0.0.1:19830/savings (note: new port if previous still
# running)
```

- [ ] Blue-banner layout, max-width visibly narrower than happy page.
- [ ] Heading: `No dispatches recorded yet`.
- [ ] CTA mentions all 4 worker roles: `coder`, `librarian`,
      `reviewer`, `scribe`.
- [ ] `Expected log location: <code>/tmp/no-such-file.jsonl</code>`
      shows the env-passed path verbatim.

## §3 Disabled state

```bash
MAESTRO_DISPATCH_LOG="" maestro-webui
# Open http://127.0.0.1:19830/savings
```

- [ ] Amber-banner layout (warning visual; not red).
- [ ] Heading: `Telemetry is disabled`.
- [ ] Body explains `MAESTRO_DISPATCH_LOG` empty-string semantics.
- [ ] Re-enable instructions mention `unset MAESTRO_DISPATCH_LOG`.
- [ ] Methodology link present (`methodology page §7` text).

## §4 Error state

```bash
MAESTRO_DISPATCH_LOG=/tmp/some-existing-directory maestro-webui
# Where /tmp/some-existing-directory is a real directory.
# Open http://127.0.0.1:19830/savings
```

- [ ] Red-banner layout (error visual).
- [ ] Heading: `Could not read the dispatch log`.
- [ ] Resolved path surfaced via `<code>` element.
- [ ] Exception text rendered inside `<pre>` block (mono-spaced).
- [ ] Exception message includes either `Is a directory` or `Errno 21`
      depending on platform (macOS / Linux).
- [ ] "Common causes" paragraph present below the diagnostic.

## §5 Cross-state checks

- [ ] **Dev tools / Console**: no JS errors on any of the 4 pages
      (open Chrome/Safari/Firefox dev tools, refresh, check Console).
- [ ] **Dev tools / Network**: `/savings` returns HTTP 200 for ALL 4
      states (no 4xx / 5xx).
- [ ] **View-source on happy page**: HTML is well-formed (no
      `{{ ... }}` Jinja leakage, no obvious truncation).
- [ ] **Page title** (browser tab) reads `Maestro · Dispatch Savings`
      for the 3 non-error states; the error state's tab reads
      `Maestro · Dispatch Savings — Error`.

## §6 Verification gates

After all checks above pass:

- [ ] No console JS errors anywhere.
- [ ] HTTP 200 for all 4 states (no degraded path 5xx'd).
- [ ] Numbers on happy page match `docs/savings.md` exactly.
- [ ] Visual hierarchy reads correctly — no broken styles, no overlap.

If anything fails: **file a follow-up issue with screenshot, state, and
the failed bullet from this checklist**. Do not patch during smoke.
