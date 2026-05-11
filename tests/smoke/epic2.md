<!-- Epic 2 手动验收清单 (manual verification checklist; automated checks in epic2_smoke.sh) -->

# Epic 2 手动验收清单

## 1. 前置条件 (Pre-requisites)

- [ ] `pip install -e .` 已在当前环境成功执行
- [ ] 没有其他 `maestro-webui` 进程在运行（如有，先 `kill`）

## 2. 新建项目流程（浏览器走查）

- [ ] 运行 `mkdir /tmp/newproj && cd /tmp/newproj && maestro-webui`
- [ ] 在浏览器中打开打印的 URL（如 `http://127.0.0.1:8XXX`）
- [ ] 访问 `/scaffold`，输入路径 `/tmp/newproj`，选择"新建项目（空目录）"，点击"查看计划"
- [ ] 确认显示 4 行，操作均为"创建"；前置检查全部 ✓；按钮"应用计划"可用
- [ ] 展开 `CLAUDE.md` 行（点"展开"按钮），钻取详情显示要追加的 maestro section
- [ ] 点击"应用计划"，结果页显示"成功 4 个文件，失败 0 个文件"
- [ ] 确认 3 秒后自动跳转到 wizard 页面（看到"3 秒后跳转到团队配置..."提示）
- [ ] 完成 wizard 4 步流程，确认 `.maestro/team.yaml` 已生成

## 3. 接入现有项目流程（浏览器走查）

- [ ] `cd /tmp && git init takeover-test && cd takeover-test && git commit --allow-empty -m init`
- [ ] 在该目录中运行 `maestro-webui`
- [ ] 访问 `/scaffold`，输入路径 `/tmp/takeover-test`，模式选择"接入现有项目"，提交
- [ ] 确认显示 2 行，操作均为"创建"
- [ ] 点击"应用计划" → 跳转到团队配置 → 完成 wizard
- [ ] 验证仓库未生成 `BUILD_LOG.md` / `docs/journal/` / `docs/governance.md`

## 4. 部分应用失败 + 幂等恢复

- [ ] 在干净的 git 仓库中开始 take-over 流程，**应用计划之前**：`chmod 444 .` 让根目录不可写
- [ ] 点击"应用计划"，预期至少一个 `file_failed`，"成功 < 期望数"
- [ ] `chmod 755 .` 恢复写权限，重新点击"应用计划"
- [ ] 第二次应用应该幂等完成（NOOP 已写入的、CREATE 缺失的）

## 5. Wizard 自动跳转 UX 主观检查

- [ ] 点击"应用计划"成功后，3 秒倒计时是否合适？记录主观感受供 v0.0.4 调整
- [ ] "立即配置团队"按钮（不等 3 秒）是否容易看到？

## 6. CLAUDE.md 已存在（用户内容保留）

- [ ] 在一个 git 仓库中预先写入 `CLAUDE.md`，含 `# My Project\n\nMy own content` 等用户内容
- [ ] take-over 流程 → 应用计划
- [ ] 检查 `CLAUDE.md` 内容：
  - 用户原有内容（如 `# My Project`）在文件开头未被替换
  - 文件中出现 `<!-- maestro:start v=1 --> ... <!-- maestro:end v=1 -->` 区段
  - 区段在用户内容之后（不是开头）

## 7. CLAUDE.md 已有 maestro section（冲突 UX）

- [ ] 仓库中预先写一个 CLAUDE.md，含手动构造的 `<!-- maestro:start v=2 -->...<!-- maestro:end v=2 -->` 区段
- [ ] take-over → plan 显示该行为"冲突"，conflict reason 描述为"版本不匹配"
- [ ] 展开钻取，确认只有"打开文件"按钮，**没有"覆盖"或"强制"按钮**
- [ ] 应用按钮显示为"请解决冲突"且为 disabled

## 8. MCP coder dispatch end-to-end（需要 Claude Code 会话）

- [ ] 在一个 maestro-scaffolded 项目（已完成 wizard）中启动 Claude Code
- [ ] 让 Claude Code 调用 `mcp__maestro__coder` 写一段简单代码
- [ ] 验证 dispatch 使用了 wizard 写入的 team.yaml 中配置的 model

---

完成上述清单全部勾选后，Epic 2 手动验收通过。
