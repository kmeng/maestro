<!-- Epic 8 手动验收清单 (manual portion; automated portion in epic8_smoke.sh) -->

# Epic 8 手动验收清单

> 自动化部分跑 `bash tests/smoke/epic8_smoke.sh`，覆盖工具注册、schema 约束、
> handler 的 input_validation 路径（无网络、无真实 LLM 调用）。
>
> 本清单专注于：(a) 真实 MCP client 端的端到端验证（需要 DEEPSEEK_API_KEY），
> (b) 外部非 Maestro 项目场景（见 `epic8_external.md`），(c) Web UI 走查（无新页面，
> Epic 9 之前 Web UI 不展示 verifier/spec_writer 行）。

## 1. 前置条件 (Pre-requisites)

- [ ] `pip install -e .` 已成功
- [ ] `.env` 包含 `DEEPSEEK_API_KEY`
- [ ] 自动化烟测 `bash tests/smoke/epic8_smoke.sh` 全部 PASS

## 2. MCP 工具列表 (AC3 + AC4)

- [ ] 在 Claude Code 中跑 `/mcp`，确认 maestro server 列出 6 个 role tools + job_status：
  - `coder` / `librarian` / `reviewer` / `scribe` / `verifier` / `spec_writer` / `job_status`
- [ ] `librarian` 的 inputSchema 包含 `file_paths` 字段（type: array of strings）
- [ ] `scribe` 的 required = `["diff", "purpose"]`（不再 issue_number/title/body/convention）
- [ ] `verifier` 的 required = `["claims"]`，properties 含 `file_paths` 和 `document_text`
- [ ] `spec_writer` 的 required 含 `task_description`/`acceptance_criteria`/`upstream_contracts`/`output_files`/`language`

## 3. librarian + file_paths 真实 dispatch (T8.1 AC2 + AC5)

- [ ] 在 Claude Code 中触发 librarian 用 `file_paths` 读 2-3 个仓库文件
- [ ] dispatch 完成，输出含 `=== FILE: <path> ===` 分隔头
- [ ] dispatch-log.jsonl 出现 `tool: "librarian"` 行
- [ ] **超限测试**：拼出 > 80KB 合计长度的 `file_paths` 输入 → 返回 `document_too_large` 错误，无 model 调用计数

## 4. verifier 真实 dispatch (T8.2 AC3 + AC4 + AC5)

- [ ] 在 Claude Code 中触发 verifier，提供 3 个 claims + 1 个源文件
- [ ] 输出 `verifications: [...]`，每项 status ∈ {verified, incorrect, ambiguous}
- [ ] 输出 `_banner` 含 "verifier"
- [ ] dispatch-log.jsonl 出现 `tool: "verifier"` 行
- [ ] `python scripts/render_savings.py` 渲染表格里 verifier 列正确（'v' 计数）

## 5. spec_writer 真实 dispatch (T8.3 AC3 + AC4 + AC5)

- [ ] 在 Claude Code 中触发 spec_writer，提供完整结构化输入
- [ ] 输出 `{spec, verification_checklist, concerns}` 三键齐全
- [ ] `verification_checklist` 至少 1 项 / 每个 `output_files`
- [ ] dispatch-log.jsonl 出现 `tool: "spec-writer"` 行（注意 hyphen）
- [ ] `python scripts/render_savings.py` 渲染表格里 spec-writer 列正确（'w' 计数）

## 6. scribe 新 schema 真实 dispatch (T8.8 AC1 + AC5)

- [ ] 在 Claude Code 中触发 scribe 用新 schema：`diff` + `purpose` + 可选 `style`
- [ ] 不传 issue_number → dispatch 成功；telemetry 行 issue_number 字段为 null
- [ ] 传 `style="PR description"` → 输出 commit_message + pr_title + pr_body 三者非空
- [ ] 传 `style="release note"` 或 omit style → commit_message 非空，pr_title/pr_body 为空字符串

## 7. team.yaml 不受 Epic 8 影响 (T8.2 backward compat)

- [ ] 现有 `team.yaml` 文件（4 个 role）仍然加载成功
- [ ] 尝试在 team.yaml 加 verifier 或 spec-writer 项 → TeamConfig 校验失败（"roles must contain exactly"）
- [ ] 缺 team.yaml 时，coder/librarian/reviewer/scribe 走 DEFAULT_MODELS fallback；verifier/spec_writer 同样走 DEFAULT_MODELS（但不读 team.yaml，bypass）

## 8. 外部项目验证

转到 `tests/smoke/epic8_external.md`，在一个非 Maestro 项目中跑 checklist。

## 9. Sign-off

- [ ] 上述全部勾选
- [ ] 在 `docs/journal/2026-05-17-epic8-close.md` 记录手测发现
