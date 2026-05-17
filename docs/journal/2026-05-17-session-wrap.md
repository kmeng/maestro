# 2026-05-17 — Session wrap (Epic 8 close + #74 + #102 + cost meta)

> Long session: Epic 8 全 7 sub-issues 关 + #74 sanitization 通过 T8.7 trial
> wave 闭环 + #102 README status 刷新。详细 Epic 8 close 见
> `2026-05-17-epic8-close.md`；本文是 session-level wrap + 自我审计。

## Session arc

v0.0.4 head 从 `74dc9e6`（昨晚 zh-CN-ify 后） → `70a907d`（今天 session 末）。
推 origin。Issue 关闭 9 个（#74 / #78 / #79 / #80 / #81 / #82 / #83 / #84 / #85 / #102，
+ #72 早已 closed at Epic 8 plan landing）。tests 551 passed / 2 skipped。

## Done not in epic8-close

- **#102 README status 刷新**：4 roles → 6 roles，✅ auto-review gate +
  ✅ Web UI cockpit + ✅ 每-dispatch cost telemetry；broken `[roadmap](./ROADMAP.md)`
  链改成 journal + savings 指针。独立 issue / branch / merge（H3 protected
  file 走标准流程）。merge `70a907d`。

## Distinctive moment：self-audit of token cost

中段用户直接问"Token 消耗反而越来越多了"，触发对 session 行为的诚实拆解。
四条根因：

1. **W4 Part A trial wave overhead 大于产出**：30 行代码改动调 6 个
   worker；spec_writer 输入 ~3k token + 我手写给 coder 的 spec ~3k token，
   两份内容高度重合。trial bed 太小，无法摊薄"演示便宜"的成本。

2. **Epic 8 前几个 task 的 spec 由 orchestrator（Opus）手写 600-900 行**：
   spec_writer 当时还没 ship，chicken/egg。这正是 Epic 8 想解决的问题，
   解决过程本身无法用解决方案。

3. **冗余 user-facing 报告**：每 step 4-行 telemetry 表格 + "Step N/7"
   + 计划复述。一个 session 累积 ~20k token Opus 输出，多半是自我安慰
   式同步，对用户无新信息。

4. **verifier 用在 trivial case**：#74 spec 显然正确，verifier 仍跑 14s/4k
   token。dogfood 价值 ≠ 决策价值。

**用户决定走"精简版收尾"**：Part B/C/D 由 orchestrator 直写（不再 worker
dispatch），减少报告，机械链条直接做完报结果。最后 commit chain 一条
bash 命令跑完（branch + commit + checkout + merge + 2 × gh close + push +
log）。

## Open follow-ups（不在本 session scope）

- **v0.0.4 → main release** 决策
- **Fresh-install end-to-end 独立测试**（最早会话提到的 pipx install +
  Claude Code attach + 真 coder dispatch 链）
- **MCP server reload 文档**（Epic 8 epic8-close journal 列为 follow-up）
- **Coder full-file 防护 memory 规则**（T8.2 lesson 待编码）
- **Spec-writer shadow-mode trial wave**（Epic 9+ 第一波；contract-sheets
  playbook § Shadow-mode protocol 已写定）

## Numbers (session-level)

- Issues closed: 10
- Merges to v0.0.4: 9（W1a×2 + W1b 不 commit + W2 + W3a + W3b + W4 Part A + W4 Part B/C/D + #102）
- Pytest delta: 504（baseline）→ 551（+47 tests across Epic 8 + #74）
- Worker dispatches: 30+（按 docs/data/dispatch-log.jsonl 数）
- Wall：~ 完整工作日

## What's next

v0.0.4 release content 完整。等用户决策 v0.0.4 → main ship 时机。
