# Design 88: Web UI all-pages redesign — Dashboard Cockpit

**Epic**: #88
**Status**: approved 2026-05-15
**Author**: orchestrator
**ADR**: [ADR-0012 — Web UI design tokens](../adr/0012-webui-design-tokens.md)

This document is the authoritative source for every Epic 9 sub-task.
The page-by-page wireframes below define the *contract* each task PR
satisfies. The design-token reference at the bottom is the contract
T9.1 implements.

---

## 1. Goal

Replace the placeholder landing page and the ad-hoc per-page inline
CSS that accumulated through Epics 0–7 with a unified, real-data
**Dashboard Cockpit** across all eight Web UI pages.

Two readers must be served by the same surface:

- **Dogfooding user (Maestro the project itself)**: opens
  `localhost:19830` multiple times a day; wants information density —
  today's dispatch count, savings delta, in-flight job, open
  problems — at a glance.
- **General user (anyone running maestro on their project)**: opens
  `/` on first run; wants to know what to do next. The entry-tile
  grid covers this.

Both flows share the same `/`. Data sources degrade gracefully: a
fresh `.maestro/` with no dispatch log yields a "Get started" CTA in
place of the now-running panel.

---

## 2. Non-goals

- **No new features**. Any functional change (new route, new data
  source, new worker tool) belongs to a different epic.
- **No backend route signature changes**. Existing view modules keep
  their handlers; only template + minor data-shape changes allowed.
- **No dark mode** (v1).
- **No responsive below 1024px** (v1; sidebar icon-collapse is
  acceptable degradation, full mobile is future work).
- **No per-task savings table** (out-of-scope per Epic 7 boundary;
  per-task data lives in `docs/savings.md`).
- **No i18n beyond what's already there**. Chinese labels stay where
  they are; English secondary.

---

## 3. Distinguishing dogfooding-user vs general-user

(per `feedback_distinguish_user_from_general.md`)

This is a recurring confusion in Maestro. Spelled out here once so
no sub-task gets it wrong:

| Surface | Dogfooding-user need | General-user need |
|---|---|---|
| `/` Overview | "Did anything break today? How much did we save?" | "I just installed this — what now?" |
| `/team-catalog` | Quick edit | First-time team setup link → wizard |
| `/wizard` | Rarely used after setup | The primary onboarding flow |
| `/scaffold` | Used during new-project bootstrap | Same |
| `/live` | Watch a dispatch as it runs | Same |
| `/history` | Investigate past dispatches | Audit own usage |
| `/savings` | Headline savings + per-role/time tables | Same data, same view |
| `/problems` | Worker-quality flags, spec drift | Configuration issues, bad models |

When a page has divergent needs (`/`, `/team-catalog`), the design
must show both — empty-state copy is where the general-user signal
lives.

---

## 4. Design tokens

Locked in [ADR-0012](../adr/0012-webui-design-tokens.md). One-page
summary reproduced here for citation convenience.

### 4.1 Palette

```css
:root {
  --bg: #fafafa;
  --panel: #ffffff;
  --panel-tint: #eff6ff;
  --border: #ececef;
  --border-strong: #d4d4d8;
  --fg: #18181b;
  --muted: #71717a;
  --accent: #2563eb;
  --accent-tint: #eff6ff;
  --green: #16a34a;
  --orange: #ea580c;
  --red: #dc2626;
}
```

### 4.2 Typography

- Body: 14px / 400 / `Inter, -apple-system, "Noto Sans CJK SC"`.
- H1 page title: 22px / 600 / -0.02em.
- Panel header: 13px / 600.
- Sub-title / muted small: 13px / 400 / `var(--muted)`.
- Label: 12px / 500 / `var(--muted)`.
- KPI value: 26px / 600 / -0.02em.
- Mono: `SF Mono, JetBrains Mono, Menlo` 13px (IDs, counts, timestamps).

### 4.3 Spacing

4px base; legal values: 8 / 12 / 16 / 18 / 20 / 24 / 28 / 32 / 40.

### 4.4 Layout

- Sidebar: fixed 220px left, `--panel` bg, right `1px solid var(--border)`.
- Main: `padding: 32px 40px`, independent scroll.
- Panel: `1px solid var(--border)`, `border-radius: 10px`,
  padding 18–20px.

### 4.5 Floor

Minimum viewport **1024 × 720**. Below 1024px wide, sidebar
collapses to icon-only (T9.1 ships this).

---

## 5. Base template

`maestro/webui/templates/_base.html` — every page extends it.

### 5.1 Structure

```jinja
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Maestro · {% block title %}{% endblock %}</title>
  <link rel="stylesheet" href="/static/maestro.css">
  {% block extra_head %}{% endblock %}
</head>
<body>
  <aside class="sidebar">
    <div class="brand">
      <div class="brand-dot"></div>
      <div class="brand-name">Maestro</div>
    </div>
    <div class="brand-sub">v{{ version }} · localhost</div>
    <nav class="nav">
      <a href="/" {% if nav_active == "overview" %}aria-current="page"{% endif %}>Overview</a>
      <a href="/team-catalog" {% if nav_active == "team" %}aria-current="page"{% endif %}>Team</a>
      <a href="/scaffold" {% if nav_active == "scaffold" %}aria-current="page"{% endif %}>Scaffold</a>
      <a href="/live" {% if nav_active == "live" %}aria-current="page"{% endif %}>Live</a>
      <a href="/history" {% if nav_active == "history" %}aria-current="page"{% endif %}>History</a>
      <a href="/savings" {% if nav_active == "savings" %}aria-current="page"{% endif %}>Savings</a>
      <a href="/problems" {% if nav_active == "problems" %}aria-current="page"{% endif %}>Problems</a>
    </nav>
    <div class="spacer"></div>
    <div class="sb-footer">
      <span class="dot-ok"></span> healthy
    </div>
  </aside>
  <main class="main">
    {% block content %}{% endblock %}
  </main>
  <script src="/static/vendor/htmx.min.js" defer></script>
  {% block extra_scripts %}{% endblock %}
</body>
</html>
```

### 5.2 Exposed blocks

| Block | Used by |
|---|---|
| `title` | Every page (sets `<title>`). |
| `nav_active` | A `{% set nav_active = "..." %}` at top of each page — controls active-nav highlight. |
| `extra_head` | Pages needing extra `<link>` / `<meta>`. |
| `content` | Mandatory page body. |
| `extra_scripts` | Pages needing page-local JS (e.g., Live's EventSource). |

### 5.3 Sidebar variants

For htmx fragment responses, **do not** extend `_base.html` — those
returns are partial HTML swapped into a target. Use shared CSS
classes inline.

---

## 6. Components

The vocabulary every page reaches for. T9.1 ships the CSS; later
tasks compose from this list.

### 6.1 Page header

```html
<h1 class="page-h1">Overview</h1>
<div class="page-sub">Friday, May 15 · all systems nominal</div>
```

### 6.2 KPI strip

A horizontal grid of 3–4 tiles at top of a page.

```html
<div class="kpis">
  <div class="kpi">
    <div class="kpi-label">Dispatches today</div>
    <div class="kpi-value">14</div>
    <div class="kpi-delta up">↑ 3 vs yesterday</div>
  </div>
  ...
</div>
```

States: `.kpi-delta.up` (green), `.kpi-delta.down` (orange),
`.kpi-delta.neutral` (muted).

### 6.3 Panel

```html
<section class="panel">
  <header class="panel-h">
    <h2 class="panel-title">Dispatches · last 7 days</h2>
    <div class="panel-meta">147 total</div>
  </header>
  <!-- panel body -->
</section>
```

### 6.4 Entry tile

For navigation cards (the 6 tiles on `/`).

```html
<a href="/team-catalog" class="entry">
  <div class="entry-title">Team</div>
  <div class="entry-desc">Pick the model behind each role.</div>
  <div class="entry-cta">4 roles configured →</div>
</a>
```

### 6.5 Now-running panel

```html
<div class="run">
  <div class="pulse"></div>
  <div class="run-info">
    <div class="run-main">coder · T3.8 graph-view</div>
    <div class="run-sub">deepseek-coder · 3,420 tok · ~$0.03</div>
  </div>
</div>
```

Empty state for this panel: replace `.run` with `.empty-run` and
copy "No dispatch running — last finished 14m ago".

### 6.6 Status badges

| Class | Label | Color |
|---|---|---|
| `.badge-ok` | ✓ 成功 / done | `--green` |
| `.badge-fail` | ✗ 失败 / failed | `--red` |
| `.badge-refused` | ⊘ 已拒绝 / refused | `--orange` |
| `.badge-fallback` | ↩ 已降级 / fallback | `--orange` |
| `.badge-running` | ◐ 进行中 / running | `--accent` |
| `.badge-create` | + create | `--green` |
| `.badge-overwrite` | ~ overwrite | `--orange` |
| `.badge-skip` | – skip | `--muted` |

### 6.7 Form fields

```html
<label class="field">
  <span class="field-label">Role</span>
  <input class="field-input" type="text" name="role">
  <span class="field-error">required</span>
</label>
```

### 6.8 Buttons

`.btn` (default) · `.btn-primary` (accent) · `.btn-danger` (red) · `.btn-ghost`.

### 6.9 Empty state

```html
<div class="empty-state">
  <div class="empty-icon">…</div>
  <div class="empty-title">Nothing to flag</div>
  <div class="empty-body">A quiet day. Dispatches today: 14, all green.</div>
</div>
```

### 6.10 Table

```html
<table class="data-table">
  <thead><tr><th>...</th></tr></thead>
  <tbody><tr><td>...</td></tr></tbody>
</table>
```

Row hover, sticky header where useful. `.data-table--dense` variant
for high-row-count tables like `/history`.

---

## 7. Page wireframes

### 7.1 `/` Overview (T9.3)

```
┌───────────┬────────────────────────────────────────────────────┐
│ [sidebar] │ Overview                                            │
│           │ Friday, May 15 · all systems nominal                │
│           │                                                     │
│           │ ┌────┐ ┌────┐ ┌────┐ ┌────┐                          │
│           │ │KPI1│ │KPI2│ │KPI3│ │KPI4│                          │
│           │ └────┘ └────┘ └────┘ └────┘                          │
│           │                                                     │
│           │ ┌─Dispatches · last 7d ──┐ ┌─Now running ──┐         │
│           │ │   ▁▂▃▅▃▆▇             │ │ ● coder T3.8   │         │
│           │ │                       │ │ deepseek 3420t │         │
│           │ └────────────────────────┘ └───────────────┘         │
│           │                                                     │
│           │ ┌───────┐ ┌────────┐ ┌──────┐                        │
│           │ │ Team  │ │Scaffold│ │ Live │                        │
│           │ ├───────┤ ├────────┤ ├──────┤                        │
│           │ │History│ │Savings │ │Probl │                        │
│           │ └───────┘ └────────┘ └──────┘                        │
└───────────┴────────────────────────────────────────────────────┘
```

Data source: `GET /api/overview` (T9.2).

Empty state (no dispatch log yet): KPIs all zero, Now-running panel
replaced with "Get started → /wizard" CTA, sparkline shows 7 empty bars.

### 7.2 `/team-catalog` (T9.4)

```
[sidebar] | Team
          | 4 roles · last edited 2d ago
          |
          | ┌────────────────────────────────┐
          | │ Role     Provider   Model   ⋯  │
          | │ coder    deepseek   ds-coder ⋯ │
          | │ reviewer anthropic  haiku    ⋯ │
          | │ ...                           │
          | └────────────────────────────────┘
```

Per-row edit lives at `/team-catalog/edit/{role}` — modal-feel page
inside the same layout (sidebar visible).

Empty-state (no team.yaml): "No team configured. Start the wizard."
with a `.btn-primary` to `/wizard`.

### 7.3 `/wizard` (T9.5)

```
[sidebar] | Team setup wizard
          | Step 2 of 4
          |
          | ● ─── ● ─── ○ ─── ○        (progress)
          | Provider  Models  Quotas  Save
          |
          | ┌────────────────────────────────┐
          | │ Form for current step          │
          | │ [Back]              [Continue] │
          | └────────────────────────────────┘
```

Progress indicator uses the same accent token. Each step is an htmx
fragment swap — the surrounding chrome (sidebar, h1, progress) does
not redraw.

### 7.4 `/scaffold` (T9.6)

Two screens swap based on whether a plan has been generated:

**Picker** (no plan yet):

```
[sidebar] | Scaffold
          | Choose a template, give it a project path
          |
          | ┌─ Template ──────────┐
          | │ ○ fastapi-mvp        │
          | │ ○ fastapi-llm-agent  │
          | │ ○ ...                │
          | └──────────────────────┘
          | [Project path: _______]
          | [Generate plan →]
```

**Plan** (after generate):

```
[sidebar] | Scaffold · fastapi-mvp → /Users/.../my-app
          |
          | ┌──────────────────────────────────────┐
          | │ + create  app/main.py                │
          | │ ~ overwrite README.md                │
          | │ – skip     .gitignore (exists)       │
          | │ ...                                  │
          | └──────────────────────────────────────┘
          | [Cancel]                  [Apply plan]
```

After apply: success-summary panel listing files written, with link
back to the picker.

### 7.5 `/live` (T9.7)

```
[sidebar] | Live
          | Streaming dispatch events
          |
          | ┌─ Running ──────────────────────────┐
          | │ ● coder T3.8 graph-view  1m 22s    │
          | │ ● reviewer T3.7          0m 38s    │
          | └────────────────────────────────────┘
          |
          | ┌─ Completed (last 10) ──────────────┐
          | │ ✓ scribe commit-T3.6  22s  $0.01    │
          | │ ✓ librarian read-adr  14s  $0.01    │
          | │ ...                                │
          | └────────────────────────────────────┘
```

EventSource bound on page load (existing); rows move from Running to
Completed on terminal events.

### 7.6 `/history` (T9.8)

```
[sidebar] | History
          | 147 dispatches · last 30 days
          |
          | ┌─ table ─────────────────────────────────────────┐
          | │ ●  Time     Role      Model      Dur   Cost  …  │
          | │ ✓  14:30:41 reviewer  haiku      38s   $0.04   ▾│
          | │   (details drill-down)                          │
          | │ ↩  14:18:55 librarian (fallback) 14s   $0.01    │
          | │ ...                                             │
          | └─────────────────────────────────────────────────┘
```

Dense table variant. Status icons in column 1 use shared badge
classes. `<details>` drill-down for full input/output.

### 7.7 `/savings` (T9.9)

```
[sidebar] | Savings
          | 147 dispatches · 2026-04-10 → 2026-05-15
          |
          | ┌────┐ ┌────┐ ┌────┐ ┌────┐
          | │$tot│ │$svd│ │ %  │ │date│   (KPI strip)
          | └────┘ └────┘ └────┘ └────┘
          |
          | ┌─ By role ──────────────┐ ┌─ By day ───┐
          | │ role   ct  cost  saved │ │  bar chart │
          | │ ...                    │ │  per-day   │
          | └────────────────────────┘ └────────────┘
```

Three degraded states (empty / disabled / error) each get their own
`.empty-state` block with copy + CTA per Epic 7's design.

### 7.8 `/problems` (T9.10)

```
[sidebar] | Problems
          | 2 open · 1 worker-quality · 1 config-invalid
          |
          | ┌─ Failures ─────────────────────────┐
          | │ (rows)                             │
          | └────────────────────────────────────┘
          |
          | ┌─ Refusals (config-invalid) ────────┐
          | │ (rows)                             │
          | └────────────────────────────────────┘
          |
          | ┌─ Fallbacks (config-absent) ────────┐
          | │ (grouped by role)                  │
          | └────────────────────────────────────┘
```

Whole-page empty state when all three are empty: positive copy
("Nothing to flag — quiet day").

---

## 8. Data sources

### 8.1 Overview KPIs (T9.2 — `/api/overview`)

| Field | Source |
|---|---|
| `today.dispatches` | `scan_log(.maestro/logs/dispatch.jsonl)` filtered to `started_at_iso[:10] == today` |
| `today.savings_usd` | `compute_costs()` summed over today's rows after `filter_superseded` |
| `today.delta_dispatches_vs_yesterday` | today's count − yesterday's count |
| `cumulative.dispatches` | `len(filter_superseded(read_rows_with_skipped()[0]))` |
| `cumulative.savings_usd` | sum of `compute_costs()` `saved_usd` field |
| `cumulative.savings_pct` | `saved / opus_total * 100` |
| `now_running` | latest `DispatchStartEvent` per `request_id` with no matching End / Failed event AND `elapsed_s < 600` |
| `active_workers` | distinct roles in the now-running set |
| `open_problems` | count from `problem_panel`'s aggregation (failures + refusals + grouped fallbacks) |
| `sparkline_7d` | `scan_log` grouped by day, last 7 days, oldest first |

Constraints:

- Empty log → all numeric fields zero, `now_running: null`, sparkline
  has 7 entries with `count: 0`. **Never 500s.**
- Stale in-flight (>10 min without End / Failed): treated as
  abandoned, excluded from `now_running` and `active_workers`.
- No caching. Recompute each call.

### 8.2 Per-page data sources

Each page keeps its existing data path; this redesign is a re-skin.

- `/team-catalog` → `paths.user_team_path()` → `team.yaml`
- `/wizard` → POST endpoints write to `team.yaml`
- `/scaffold` → `scaffold.io` + template registry
- `/live` → `/api/dispatch_log/stream` SSE
- `/history` → `scan_log` (one-shot)
- `/savings` → `maestro.savings`
- `/problems` → `problem_panel.py` scan

---

## 9. File layout

New files:

```
maestro/webui/
  static/
    maestro.css                       (T9.1)
  templates/
    _base.html                        (T9.1)
  overview_api.py                     (T9.2)

docs/
  adr/0012-webui-design-tokens.md     (T9.0 — landed)
  design/88-webui-redesign.md         (T9.0 — this file)
```

Modified files (each in its own sub-task):

```
maestro/webui/__init__.py             (route wiring for overview_api)
maestro/webui/templates/index.html    (T9.3)
maestro/webui/templates/team_catalog*.html   (T9.4)
maestro/webui/templates/wizard*.html  (T9.5)
maestro/webui/templates/scaffold*.html (T9.6)
maestro/webui/templates/live.html     (T9.7)
maestro/webui/templates/history.html  (T9.8)
maestro/webui/templates/savings*.html (T9.9)
maestro/webui/templates/problem_panel.html (T9.10)
```

---

## 10. Task plan & critical path

(Mirror of Epic #88 body, kept here so the doc is self-contained.)

```
              T9.0  docs landing
                │
        ┌───────┴───────┐
        │               │
       T9.1            T9.2
   base template    /api/overview
        │               │
        └───────┬───────┘
                │
   ┌──────┬─────┴─────┬──────┬──────┬──────┬──────┐
  T9.3  T9.4         T9.5   T9.6   T9.7   T9.8   T9.9  T9.10
  Over  team-cat    wizard  scaff  live   hist   savg  problems
   │
   └─────────────────────────────────────────────────────┐
                                                         │
                                                       T9.11
                                                  e2e + journal + close
```

Critical path: T9.0 → T9.1 → T9.3 → T9.11.

Wave plan:

| Wave | Tasks | Notes |
|---|---|---|
| W0 | T9.0 | orchestrator-authored docs PR |
| W1 | T9.1, T9.2 | file-disjoint, parallel coder dispatches |
| W2 | T9.3 → T9.10 | 8 file-disjoint redesigns; dispatch in two batches of 4 to keep token budget sane |
| W3 | T9.11 | final |

Per-task contracts live in each sub-issue body — this design doc is
the shared reference they cite.

---

## 11. Acceptance criteria for the Epic

Aggregated from per-task ACs:

- [ ] ADR-0012 merged.
- [ ] All 8 pages render extending `_base.html`.
- [ ] Zero un-justified inline `<style>` blocks remain.
- [ ] `/api/overview` returns the contract shape; `/` consumes it.
- [ ] All visible numbers come from real data sources; no hardcoded
      placeholders in rendered HTML.
- [ ] Empty-state copy correct for every page when run against a
      fresh `.maestro/`.
- [ ] All eight routes return 200 in smoke.
- [ ] BUILD_LOG.md updated.
- [ ] `docs/savings.md` refreshed.
- [ ] Journal entry for the epic.

---

## Appendix A. Future work consciously deferred

- Dark mode (token structure pre-empts it).
- Mobile / <1024px responsive.
- Live page WebSocket protocol upgrade.
- Internationalization framework.
- Per-task savings table on `/savings`.
- Search / filter on `/history`.
- Cost projection page (would reuse KPI + sparkline primitives).
