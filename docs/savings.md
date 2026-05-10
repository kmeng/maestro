# Dispatch Savings

Across 12 closed task(s), 25 dispatch(es) captured 158,098 total tokens. At provider rates, this cost $0.07; estimated baseline at Opus rates would be $6.47 — a conservative lower-bound saving of $6.40 (98.9%). All numbers in the table below come from worker-API responses captured at dispatch time; see methodology for what is measured vs estimated.

## Per-Task Savings

| Task | Closed | Issue | Dispatches | Tokens | Wall (s) | Est. Opus $ | Worker $ | Saved | Status |
|------|--------|-------|------------|--------|----------|-------------|----------|-------|--------|
| T6.8 |  | [#64](https://github.com/kmeng/maestro/issues/64) | 1 (c1 l0 r0 s0) | 10,530 | 193 | $0.52 | $0.01 | $0.51 (98.5%) | ✓ |
| T6.7 |  | [#63](https://github.com/kmeng/maestro/issues/63) | 1 (c0 l1 r0 s0) | 2,803 | 15 | $0.10 | $0.00 | $0.10 (99.6%) | ✓ |
| T6.5 |  | [#62](https://github.com/kmeng/maestro/issues/62) | 3 (c0 l3 r0 s0) | 24,029 | 114 | $0.77 | $0.00 | $0.77 (99.6%) | ✓ |
| T6.3 |  | [#59](https://github.com/kmeng/maestro/issues/59) | 1 (c1 l0 r0 s0) | 17,045 | 478 | $0.77 | $0.01 | $0.76 (98.5%) | ✓ |
| T6.2 |  | [#58](https://github.com/kmeng/maestro/issues/58) | 1 (c1 l0 r0 s0) | 15,114 | 384 | $0.68 | $0.01 | $0.67 (98.5%) | ✓ |
| T6.1 |  | [#57](https://github.com/kmeng/maestro/issues/57) | 1 (c1 l0 r0 s0) | 5,000 | 60 | $0.23 | $0.00 | $0.22 (98.5%) | ⚠ |
| T5.3 |  | [#55](https://github.com/kmeng/maestro/issues/55) | 2 (c1 l1 r0 s0) | 7,000 | 41 | $0.32 | $0.00 | $0.31 (99.3%) | ⚠ |
| T5.2 |  | [#54](https://github.com/kmeng/maestro/issues/54) | 2 (c2 l0 r0 s0) | 20,000 | 180 | $0.90 | $0.01 | $0.89 (98.5%) | ⚠ |
| T5.1 |  | [#53](https://github.com/kmeng/maestro/issues/53) | 1 (c1 l0 r0 s0) | 4,470 | 28 | $0.00 | $0.00 | $0.00 (0.0%) | rate-unknown ⚠ |
| T0.3 |  | [#21](https://github.com/kmeng/maestro/issues/21) | 6 (c1 l2 r1 s2) | 24,675 | 249 | $1.11 | $0.01 | $1.10 (99.2%) | ⚠ |
| T0.2 |  | [#20](https://github.com/kmeng/maestro/issues/20) | 5 (c1 l2 r1 s1) | 24,066 | 267 | $1.08 | $0.01 | $1.07 (99.1%) | ⚠ |
| T0.1 |  | [#19](https://github.com/kmeng/maestro/issues/19) | 1 (c1 l0 r0 s0) | 3,366 | 22 | $0.00 | $0.00 | $0.00 (0.0%) | rate-unknown ⚠ |

## Per-Role Breakdown

| Role | Dispatches | Total tokens | Avg tokens/call | Avg wall (s) | Total worker $ | Total est. Opus $ |
|------|------------|---------------|-----------------|--------------|----------------|-------------------|
| Coder | 7 | 60,266 | 8609 | 184.4 | $0.04 | $2.40 |
| Librarian | 4 | 26,832 | 6708 | 32.4 | $0.00 | $0.87 |

*14 row(s) excluded from this aggregate as ⚠ estimates.*

---

*Methodology: [docs/savings-methodology.md](savings-methodology.md)*  
*Last updated: 2026-05-10T05:46:47Z*  
*Source: [dispatch-log.jsonl](data/dispatch-log.jsonl)*
