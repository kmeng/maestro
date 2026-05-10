# Savings methodology

This page documents *exactly* how the numbers in [`docs/savings.md`](savings.md)
are produced — what is measured, what is estimated, where the
limits are, and how to reproduce the page from raw data.

The audience is a skeptical external reader: someone who sees the
[BUILD_LOG.md](../BUILD_LOG.md) "10–20% of Opus" claim or the
landing page's headline saving, and wants to verify rather than
trust.

The corresponding ADR is
[`docs/adr/0010-dispatch-log-and-effectiveness-methodology.md`](adr/0010-dispatch-log-and-effectiveness-methodology.md);
the upstream design is
[`docs/design/56-effectiveness-page.md`](design/56-effectiveness-page.md).

---

## 1. What "measured" means

A field is *measured* if it comes from the worker's API response
captured at dispatch time and never recomputed. Specifically:

| Field | Source |
|-------|--------|
| `wall_s` | Wall-clock duration the dispatcher waited on the upstream API call |
| `prompt_tokens`, `completion_tokens`, `total_tokens` | The `usage` object returned by the model provider in the same response |
| `model`, `model_provider` | Static at dispatch site |
| `started_at` | Server clock at dispatch start |
| `tool` | Which worker role was invoked |

These land in `docs/data/dispatch-log.jsonl` once per dispatch
(`is_estimate: false`), in `bootstrap/maestro_server.py`'s
`_emit_dispatch_row()`. Once written, rows are append-only — no
backwriter rewrites historical numbers.

A row's `is_estimate` field is the single bit that distinguishes
this case from §2.

## 2. What "estimated" means

A field is *estimated* when it didn't come straight from a worker
API response. Estimated rows carry `is_estimate: true` and an
`est_method` string explaining the source. Three cases exist today:

1. **Opus baseline (always estimated)**. Maestro doesn't dispatch
   to Opus, so `opus_$` for any row is computed from `total_tokens
   × opus_rate`. See §3.
2. **50/50 split when only `total_tokens` is known**. Some early
   dispatches captured only the total (banner-gap era, before
   T6.1). The renderer treats these as 50% prompt / 50% completion
   when computing per-rate $; this is a neutral assumption, not a
   measurement. Rows in this state get an explicit `est_method:
   "split-50-50"`.
3. **Historical backfills (T6.5)**. Five tasks closed before
   T6.2's emit hook landed (T0.1, T5.1–3, T0.2, T0.3) get rows
   reconstructed from journal entries and best-effort token
   estimates. These carry `is_estimate: true`,
   `est_method: "backfill"`, and a `⚠` symbol in the rendered
   per-task table. The per-role aggregate footnote excludes these
   rows from averages.

Forward rows (post-T6.2) are always `is_estimate: false`.

## 3. Opus baseline formula

For every dispatch row, the renderer also computes what the *same
token count* would cost at Opus rates:

```
opus_$ = (prompt_tokens × opus_input_rate + completion_tokens × opus_output_rate) / 1_000_000
saved_$ = opus_$ − worker_$
saved_pct = saved_$ / opus_$ × 100
```

**This is a rate-based comparison, not a behavioural one.** We are
*not* claiming Opus would use the same tokens for the same task —
that's empirically variable. We are reporting "what this exact
token count would have cost at Opus rates" — a like-for-like
substitution at the rate level.

### Why this is a conservative lower bound

In practice, Opus tends to use *more* tokens than smaller models
for non-trivial tasks: longer reasoning chains, more verbose
explanations, more candidate considerations before committing to
output. The realistic Opus token count for the same task is
typically *higher* than the worker's, which would push `opus_$`
*up* and the saving *up*. Reporting the substitution at the
worker's token count therefore yields a saving that is at least
the reported one — never more flattering than reality.

### Why this is not a claim

We do not claim "Opus would produce identical output." We do not
claim "Opus would even agree with the worker's approach." Both are
plausible but unverified. We also don't run double-experiments to
calibrate per-task. The savings number is a *rate-level cost
substitution*, presented for transparency, not a quality
equivalence claim. Quality should be assessed separately
(reviewer dispatches, end-to-end smoke tests, the project's own
shipped releases).

## 4. Provider rates

Snapshot date: **2026-05-10**. Updates to this table happen as
explicit code changes to
[`scripts/render_savings.py`](../scripts/render_savings.py)
(`PROVIDER_RATES_USD_PER_M_TOKENS`) so historical pages re-render
to the same numbers if you check out an old commit.

| Model | Provider | Input ($/M tokens) | Output ($/M tokens) | Source |
|-------|----------|--------------------|---------------------|--------|
| `claude-opus-4-7` | Anthropic | 15.00 | 75.00 | <https://www.anthropic.com/pricing> |
| `deepseek-v4-pro` | DeepSeek | 0.27 | 1.10 | <https://api-docs.deepseek.com/quick_start/pricing> |
| `deepseek-v4-flash` | DeepSeek | 0.07 | 0.27 | <https://api-docs.deepseek.com/quick_start/pricing> |

If a row's `model` isn't in this table, the renderer marks the row
`⚠ rate-unknown` and excludes it from per-role aggregates.

## 5. Gaps — what is *not* measured

The savings page makes claims about **worker dispatches**. It does
**not** account for:

1. **Orchestrator-side Opus consumption**. Claude Code (the main
   session running on the user's Anthropic subscription) does
   substantial reasoning per task: reading code, planning,
   integrating worker output, writing PRs. None of that is
   captured here — Anthropic's console is the only source, and
   it isn't dispatch-attributable. Treat the headline saving as
   "savings *on the dispatched portion of the work*", not "total
   savings vs running everything on Opus."
2. **Cache hit ratios**. Provider-side prompt caching (Anthropic's
   cache, DeepSeek's context cache) reduces real costs, but the
   token counts in the JSONL are pre-cache nominal counts. Real
   dollar costs may be lower than reported `worker_$` figures.
3. **Prompt-engineering iteration cost**. When designing a
   dispatch spec, the orchestrator may iterate (rewrite specs,
   re-dispatch) before the row that makes it to the JSONL. Only
   the final dispatch is recorded; the iteration burden is
   invisible.
4. **Failed dispatches that succeed on retry**. The JSONL records
   each dispatch with its own `error` field; aggregates exclude
   error rows from saving claims, but the wall time and token
   spend on failures is real and not deducted from saving.

These gaps are documented to keep the public claim honest. None
inflate the saving — if anything, accounting for (1)–(4) would
tighten the number.

## 6. Reproducibility

The audit trail is committed to the repo:

- Renderer: [`scripts/render_savings.py`](../scripts/render_savings.py)
- Raw data: [`docs/data/dispatch-log.jsonl`](data/dispatch-log.jsonl)
- Rendered output: [`docs/savings.md`](savings.md)

To verify any version of the page:

```bash
git checkout <commit-of-interest>
python scripts/render_savings.py
diff <(git show HEAD:docs/savings.md) docs/savings.md
```

The expected output is empty — the renderer is deterministic
(sort orders fixed, `Last updated` derived from `max(started_at)`
rather than `now()`, atomic `.tmp` + rename writes). Any drift is
a bug or a rates change; see commit log of the renderer.

CI enforcement of this byte-for-byte invariant is deferred to
v0.0.4 (D9 in [#56](https://github.com/kmeng/maestro/issues/56)).

## 7. How to disable telemetry

The `MAESTRO_DISPATCH_LOG` env var has three modes
(`bootstrap/maestro_server.py:_resolve_dispatch_log_path`):

| Value | Behaviour |
|-------|-----------|
| Unset | Default path `docs/data/dispatch-log.jsonl` |
| `""` (empty string) | Telemetry **disabled** — dispatches still work, no rows written |
| Non-empty path | Redirect writes to that path (e.g., per-project log file) |

This is a path control, not a master toggle — disabling and
redirection use the same mechanism. Performance overhead of a
write is sub-millisecond per dispatch (rows are <500 bytes,
appended), so the env var exists for privacy / test-isolation, not
for performance.

## 8. Honesty key

Symbols used in [`docs/savings.md`](savings.md):

| Symbol | Meaning |
|--------|---------|
| ✓ | Measured. All numbers come from worker API responses captured at dispatch (`is_estimate: false`). |
| ⚠ | Estimated. The row is a backfill or a 50/50 token split — see §2 for which case. The number is the best honest reconstruction available, not a measurement. Excluded from per-role aggregate averages. |
| ◇ | Computed. The cell is derived from other cells via the formulas in §3 (Opus baseline, saved $, saved %). Not measured directly but determined entirely by measured/estimated inputs + the rates table. |
| — | Unavailable. The underlying data didn't exist for this row (e.g., a row from before the field was introduced). |

---

*This page is the contract between the project's claim and the
data backing it. If it's wrong, the claim is wrong; please open
an issue.*
