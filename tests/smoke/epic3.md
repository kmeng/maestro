<!-- Epic 3 手动验收清单 (manual verification checklist; automated checks in epic3_smoke.sh) -->

# Epic 3 手动验收清单

> 自动化部分跑 `bash tests/smoke/epic3_smoke.sh`，覆盖 AC1–AC7 的 curl/SSE/事件注入路径。
> 本清单专注于**浏览器走查**和需要真实 MCP 客户端的部分（AC1 真实 coder dispatch、AC8 MCP 接口未变）。

## 1. 前置条件 (Pre-requisites)

- [ ] `pip install -e .` 已在当前环境成功执行
- [ ] 没有其他 `maestro-webui` 进程在运行（如有，先 `kill`）
- [ ] 自动化烟测 `bash tests/smoke/epic3_smoke.sh` 全部 PASS

## 2. History 视图浏览器走查 (AC1 + AC2)

- [ ] 在干净 tmp 目录运行 `cd /tmp && mkdir epic3-manual && cd epic3-manual && maestro-webui`
- [ ] 浏览器打开打印的 URL，访问 `/history`
- [ ] 页面初始为空状态（无任何调度记录提示）
- [ ] 在另一终端，往 `/tmp/epic3-manual/.maestro/logs/dispatch.jsonl` 注入若干事件（参考自动化烟测的 `_emit_event` 路径），刷新页面：
  - [ ] 看到事件按时间倒序排列（最新在上）
  - [ ] 状态图标 ✓/✗/⊘/↩/◐ 显示正确，标签为中文（成功 / 失败 / 已拒绝 / 已降级 / 进行中）
  - [ ] 时长列遵循 `≥1000ms → "X.X 秒" / <1000ms → "X 毫秒" / 无 → "—"`
  - [ ] 成本列遵循 `prompt→completion tok` 或 `—`
  - [ ] 点击 `<details>` 展开，能看到完整 input/output；超过 60 字符的 summary 在 dl 中显示「（已截断）」
- [ ] 浏览器标签页 title 为 `Maestro · 调度历史`

## 3. Live 视图浏览器走查 (AC3)

- [ ] 同一 launcher 下访问 `/live`
- [ ] 页面分两个区：进行中 / 已完成
- [ ] 在另一终端发起一个**真实** coder 调用（需 Claude Code 注册了 maestro MCP server，并设置了 `DEEPSEEK_API_KEY`）：
  - 在 Claude Code 会话中触发 `coder` 工具，spec 类似「写一个 hello world Python 函数」
- [ ] 观察 Live 视图：
  - [ ] dispatch.start 后 1 秒内出现「进行中」卡片，elapsed 时间逐秒递增
  - [ ] dispatch.end 后该卡片移到「已完成」区，带 ✓ 图标
  - [ ] 浏览器标签页 title 为 `Maestro · 实时执行流`
- [ ] **断网/重连测试**：调度进行中时关闭浏览器 tab，重新打开 `/live`：
  - [ ] 历史事件不重复出现（基于 `Last-Event-ID` 续传）

## 4. Problem panel 浏览器走查 (AC4 + AC5 + AC6)

- [ ] 同一 launcher 下访问 `/problems`
- [ ] 三类分区清晰：失败的调度 / 团队配置被拒 / 团队配置缺失（降级）
- [ ] 浏览器标签页 title 为 `Maestro · 问题面板`
- [ ] **CTA 链接验证**：
  - [ ] 团队配置被拒 行的 CTA「打开团队配置修复」点击后跳转到 `/team`
  - [ ] 团队配置缺失（降级）行的 CTA「配置团队」点击后跳转到 `/wizard`
- [ ] **Per-session ack**：
  - [ ] 点击某条记录上的 ack 按钮，该行变为半透明（`.acked` class，opacity 0.4）
  - [ ] 刷新页面 → ack 状态丢失（设计上仅会话内有效，无持久化）
- [ ] **Fallback 分组验证**：注入 3 条 role+fallback_model 相同的 `dispatch.fallback.config_absent`
  - [ ] 问题面板将其折叠为 1 行带计数

## 5. v0.0.2 回归 — 无 .maestro/ 目录的项目

- [ ] 关闭当前 launcher
- [ ] `cd /tmp && mkdir epic3-no-maestro && cd epic3-no-maestro && maestro-webui`
- [ ] launcher 正常起来（不要求 `.maestro/team.yaml` 存在）
- [ ] 在 Claude Code 中触发一次 coder 调用
- [ ] 浏览器访问该 launcher 的 `/problems`：
  - [ ] 出现 fallback 行，显示「team.yaml 缺失，使用默认模型」类提示，CTA → `/wizard`
- [ ] `/history` 中能看到该 dispatch 的 start + end
- [ ] **关键**：dispatch 本身**成功返回**给 Claude Code（不是因为缺 team.yaml 就失败）

## 6. AC8 — MCP coder 接口未变

> AC 原文写 `cheap_code_gen`，实际工具名在 Epic 1 已改为 `coder`（保持 v0.0.3 命名一致）。
> 验证目标：从 Claude Code 看到的 `coder` 工具 schema 与 v0.0.2 文档一致。

- [ ] 在 Claude Code 中执行 `/mcp` 查看 maestro 注册状态
- [ ] 列出 `coder` 工具的输入 schema，对照 [`bootstrap/maestro_server.py`](../../bootstrap/maestro_server.py) 中 `CODER_TOOL` 的定义
- [ ] 字段未变（spec 字段、可选 `request_id` 等），返回值仍是 plaintext 代码 + banner 前缀

## 7. AC7 — 日志失败不挂 dispatch

> 自动化烟测覆盖了「logs 目录只读 → emit_event 走 stderr fallback」路径；此处主观确认。

- [ ] 自动化烟测 Check 7 PASS
- [ ] 主观验证：在 stderr 看到 `maestro: dispatch log ... failed: ...` 类信息，但 dispatch 返回值正常

## 8. 已知限制 / 不在本任务范围

- 老版本 stub 脚本 `scripts/dev_emit_dispatch.py` 写入的是 pre-T3.1 占位事件格式（`{ts, outcome, tool, note}`），不会被 T3.1 之后的 reader 解析；history 视图会跳过并打 `RuntimeWarning`。新事件注入请用 `epic3_smoke.sh` 内联的 `python -c` 真实事件构造方式。v0.0.4 候选：替换该 stub 为真实事件 emitter。
- SSE 端点的两个 `@pytest.mark.skip` 单元测试由本烟测的 SSE 章节覆盖（curl `--no-buffer -N` + 后台事件注入），不另行恢复。
- 旋转后的 `dispatch.<ts>.jsonl` 老文件**不会**进入 history 视图；仅当前活动文件被读取（contract sheet § 10 已记录）。
