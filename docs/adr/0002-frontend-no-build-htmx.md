# ADR-0002: Frontend — no-build HTML with htmx (and optional Alpine.js)

**Status**: accepted
**Date**: 2026-05-08
**Issue**: #12

## Context

The Web UI process introduced in Epic 0 needs to render forms (Epic 1
team composition wizard), file pickers and plan previews (Epic 2 project
scaffolding), and a live-updating list (Epic 3 execution-flow view).
ADR-0001 already chose FastAPI as the backend.

Two framing constraints:

1. **Maestro is a Python tool that ships to end users.** Pulling a
   Node.js / npm pipeline in for the UI adds a second toolchain to the
   contributor onboarding path and complicates any future packaging
   (Epic 4) — we'd either need a CI build step or commit pre-built
   bundles to git.
2. **Epic 3's interactivity is moderate, not high.** Dispatches happen
   at human-decision pace; the live view is a list whose items change
   state. No graph layout, no drag-and-drop, no high-frequency client
   computation. SPA-grade machinery is not earned.

## Decision

Ship the Web UI as **static HTML served by FastAPI**, with a small
declarative reactive layer:

- **htmx** (vendored as `htmx.min.js`) for AJAX requests and SSE → DOM
  updates. FastAPI returns HTML fragments; htmx swaps them into the page.
- **Alpine.js** (vendored as `alpine.min.js`) for tiny pockets of
  client-side reactivity (toggles, wizard step state) where vanilla JS
  would be noisy. Used sparingly and only when justified.

No build step. No `node_modules`. No CDN dependency at runtime — both
libraries are committed to the repo as single static files under
`webui/static/vendor/` (or equivalent — exact path resolved when
implementation lands).

## Alternatives considered

- **Pure vanilla JS + HTML (no htmx)** — rejected, but narrowly. htmx
  provides exactly two features Epic 3 leans on heavily — declarative
  SSE subscription (`hx-sse`) and DOM-swap-on-response — that would
  otherwise be hand-rolled `fetch` + `Element.replaceWith` calls. The
  hand-rolled version works; htmx makes it a one-line attribute. Net:
  htmx pays for itself within Epic 3 alone. If a contributor later
  finds htmx in the way, removing it is a mechanical refactor, not a
  rewrite — preserved as the fallback option.
- **SPA framework (Svelte / Vue / React)** — rejected. The UI surface
  is forms + a list. SPA frameworks are designed for richer
  client-side state than we need. Costs:
  - Node.js becomes a contributor prerequisite.
  - Packaging (Epic 4) gets a build pipeline or pre-built artifacts in
    git.
  - Schema duplication: client-side types diverge from FastAPI's
    Pydantic models or require a code-gen step.
  - The Pydantic-shared-schemas advantage from ADR-0001 partly evaporates
    once the UI no longer renders server-side.
- **Server-rendered Jinja templates only, no JS at all** — rejected.
  Works for Epics 1 and 2, breaks Epic 3. The live view needs server
  push without page reloads.

## Consequences

### Good

- **Zero build pipeline.** `pip install` and run — no Node.js, no
  npm, no `dist/` directory.
- **Audit-friendly.** Vendored JS files are small (htmx ~14KB, Alpine
  ~10KB), single-file, readable. No transitive npm dependencies.
- **Server-side rendering by default.** A lot of the UI is HTML emitted
  by FastAPI, so Pydantic schemas defined for the API are reused as the
  models the templates render. No schema duplication.
- **Epic 3's live view is simple.** htmx's `hx-sse-source` + a target
  element binds a server-sent event stream to a DOM node declaratively.
  The harder version of this (manual `EventSource` + DOM updates) stays
  available if we ever need finer control.
- **Packaging story (Epic 4) stays Python-only.** Whatever we package
  Maestro as, the UI assets are static files we already control.

### Bad / risks

- **htmx is a new idiom for contributors who haven't seen it.** Mitigation:
  htmx's attribute set is small (~10 commonly-used attributes); learning
  cost is hours, not days. The Epic 0 design doc will link to htmx's
  docs when implementation lands.
- **Limited client-side reactivity.** If a future epic genuinely needs
  rich client state (a graph editor, drag-and-drop, etc.), Alpine.js
  hits its limits and a real framework would be wanted. Trigger to
  reconsider: a feature where the htmx + Alpine combination produces
  visibly worse UX than an SPA would. Until that trigger fires, this
  ADR holds.
- **Vendored JS files mean we manually update them.** htmx and Alpine
  are stable enough that this is annual-or-less maintenance. Worth the
  trade for no-CDN-runtime-dependency.

### Reversibility

**Medium.** Removing htmx in favor of pure vanilla is a mechanical refactor
inside the templates. Replacing both with an SPA is a much bigger move —
it implies adopting a Node toolchain and rewriting the rendering layer.
Either direction is possible; neither is free.
