# ADR-0012: Web UI design tokens and shared layout

**Status**: accepted
**Date**: 2026-05-15
**Issue**: #88 (Epic 9)
**Relates to**: ADR-0002 (no-build htmx)

## Context

Through Epics 0–7 the Web UI grew page-by-page: a hero landing
(Epic 0), a wizard + team catalog (Epic 1), a scaffold flow
(Epic 2), three observability pages (Epic 3), a savings page (Epic 7).
Each page shipped with its own inline `<style>` block tuned in
isolation. By v0.0.3 ship date this had produced:

- **Visual drift**: different muted greys, paddings, font sizes,
  header treatments across pages.
- **A stale landing page**: `/` still shows the Epic-0 placeholder
  ("等待第一支乐章 · 将随 Epic 1–3 依次上演") even though Epics 1–7
  all shipped. First-run users see what looks like an unfinished
  project.
- **No vocabulary**: when a new page is added, there is no canonical
  KPI card / panel / table / empty-state to reach for.
- **Repeated work**: every page re-invents its own header strip,
  empty state, error state, button.

Epic 9 redesigns all eight pages in one go. To prevent the same
drift recurring in v0.0.5+, the design tokens and component
vocabulary need to be locked.

Five mockup directions were prototyped 2026-05-15 (archived under
`/tmp/maestro-mockups/` for the day; design discussion in journal).
The user picked **"Dashboard Cockpit"** — a Linear/Vercel-style
cool-grey + electric-blue dashboard — as the family. Reasons cited:
information density for daily dogfooding use, extensibility (the
tile-and-panel grid trivially absorbs new features), low risk of
looking janky if rendered cheaply.

## Decision

Adopt a single set of design tokens and a single shared base
template for all Web UI pages. Freeze them in this ADR so future
contributors cite a single source of truth.

### Palette (light theme — v1)

| Token | Value | Purpose |
|---|---|---|
| `--bg` | `#fafafa` | App background |
| `--panel` | `#ffffff` | Panel / card / tile surface |
| `--panel-tint` | `#eff6ff` | Subtle info-panel tint (now-running, etc.) |
| `--border` | `#ececef` | Panel border, divider |
| `--border-strong` | `#d4d4d8` | Table row divider, form field border |
| `--fg` | `#18181b` | Primary text |
| `--muted` | `#71717a` | Secondary text, labels, axis |
| `--accent` | `#2563eb` | Brand, links, active nav, primary action |
| `--accent-tint` | `#eff6ff` | Active-nav background, KPI delta-up bg |
| `--green` | `#16a34a` | Success, positive delta |
| `--orange` | `#ea580c` | Warning, negative delta |
| `--red` | `#dc2626` | Failure state, destructive action |

Dark mode is **not** shipped in v1. Tokens are CSS custom properties
on `:root`; a future `@media (prefers-color-scheme: dark)` block
can flip values without touching component CSS.

### Typography

| Use | Stack | Size / weight / tracking |
|---|---|---|
| Body | `Inter, -apple-system, "Noto Sans CJK SC", sans-serif` | 14px / 400 / 0 |
| H1 (page title) | same | 22px / 600 / -0.02em |
| H2 (panel title) | same | 13px / 600 / 0 |
| Sub-title | same | 13px / 400 / muted |
| Label | same | 12px / 500 / muted, uppercased optional |
| KPI value | same | 26px / 600 / -0.02em |
| KPI unit | same | 13px / 400 / muted |
| Mono | `"SF Mono", "JetBrains Mono", Menlo, monospace` | 13px (for IDs, counts, timestamps) |

System fallback (`-apple-system`) is the actual rendered face on
most user machines — `Inter` is named for fidelity but no webfont
is loaded (consistent with ADR-0002 no-CDN posture).

### Spacing rhythm

4px base. Component padding values land on multiples: 8 / 12 / 16
/ 18 / 20 / 24 / 28 / 32 / 40. Avoid arbitrary values; if a new
value is needed, add it to the design doc.

### Layout primitives

- **Sidebar**: fixed 220px on the left, `--panel` background, right
  border `--border`. Holds the brand block, nav, and a health
  footer. Always visible at viewport widths ≥1024px.
- **Main**: padded `32px 40px`, scrolls independently.
- **Panel**: `border: 1px solid var(--border)`, `border-radius: 10px`,
  `background: var(--panel)`, padding 18–20px.
- **KPI tile**: a Panel at smaller scale (16px padding); 4-up grid
  at top of page.
- **Entry tile**: a Panel with hover lift (`transform: translateY(-1px)`,
  border becomes `--accent`). Used as page-navigation cards.

### Layout floor

Minimum supported viewport: **1024 × 720**. Below 1024px wide the
sidebar collapses to icon-only (decision: ship icon-only collapse
in T9.1; full mobile responsiveness is out of scope for Epic 9).

### No build step

CSS lives in a single static file `maestro/webui/static/maestro.css`.
No PostCSS, no Tailwind, no Sass. This honors ADR-0002 (no
frontend build) and keeps the codebase greppable. The downside
(no @apply, no variable nesting in selectors) is acceptable at
this scale (~1k lines of CSS).

### Component vocabulary

Components and their canonical class names are enumerated in
`docs/design/88-webui-redesign.md § Components`. Adding a new
component requires editing the design doc (and ideally this ADR's
appendix).

## Consequences

**Positive**:

- One stylesheet, one base template — drift moves from "default
  state" to "would have to fight CI for it".
- Page coding becomes mostly content + Jinja blocks; CSS only
  added when a genuinely new component appears.
- KPI / panel / tile / empty-state idioms reusable across future
  features (e.g., an Epic 10 "Cost projection" page reuses the
  KPI strip primitive trivially).

**Negative**:

- One-time migration cost: 8 templates need to be rewritten in
  Epic 9. (Epic-budgeted.)
- Tokens are opinionated. Future taste shifts mean a coordinated
  update through this ADR, not piecemeal page tweaks.
- Without a build step, dead-CSS detection is manual.

**Neutral**:

- Dark mode deferred but token structure pre-empts it.
- The decision to use Inter via system stack (no webfont) sacrifices
  brand uniqueness for offline-first / no-CDN purity.

## Alternatives considered

- **Bring in Tailwind**. Rejected: forces a build step, drags in
  PostCSS, violates ADR-0002.
- **Inline CSS per page, share by copy**. Rejected: that is the
  status quo whose drift triggered this ADR.
- **External CSS framework (Pico, Bootstrap)**. Rejected: opinionated
  defaults fight the "dashboard for AI workflow" aesthetic; bundle
  size for a tool that ships an MCP server is hard to justify.
- **JavaScript framework (React, Svelte)**. Rejected: violates
  ADR-0002 by an order of magnitude; current page complexity does
  not call for it.

## Revisiting

This ADR is the contract for v0.0.4. Revisit when:

- A page genuinely needs a primitive not in the vocabulary
  (record it in the design doc; if material, amend this ADR).
- Dark mode is scheduled.
- Mobile / responsive is scheduled.
- A real frontend build pipeline becomes worth its weight (e.g.,
  if interactive features grow past what hand-written JS sustains).
