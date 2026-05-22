# Maestro

[English](README.md) | **中文**

> 编排一支异构的 AI 软件开发团队。用初级的价格,拿到资深级的产出。

Maestro 是一个开源框架,它把 Claude Code 变成一支完整 AI 软件开发团队的指挥者。与其在每个任务上都烧顶级模型的 token,Maestro 把工作按"角色 + 成本"路由给合适的专家——架构交给 Opus;实现、文档抽取、代码评审、提交信息起草这类执行型工作交给便宜的模型(目前是 DeepSeek v4-pro / v4-flash,更多提供方可插拔)。

最终效果:软件开发成本大约是纯旗舰模型工作流的 **10–20%**,并且有质量门在便宜模型出错时把它拦下来。

> 支撑这个数字的实测成本证据见 [docs/savings.md](docs/savings.md)。

---

## 为什么需要 Maestro

真实的软件团队不是十个资深架构师,而是少数资深的人带着一群中级和初级工程师,各自做最擅长的事。今天的 AI 编程工具没有体现这一点——它们要么在每一次敲键盘上都烧旗舰模型的 token,要么把所有事都降级到便宜模型、丢掉质量。

Maestro 走出了显而易见的下一步:**异构模型、按角色匹配、成本感知**。

| | 纯 Opus | 纯 DeepSeek | **Maestro** |
|---|---|---|---|
| 成本 | 💰💰💰💰💰 | 💰 | 💰💰 |
| 架构质量 | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| 样板代码产出 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| 跨文件推理 | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| 你始终掌控 | ✅ | ⚠️ | ✅ |

---

## 工作原理

Maestro 作为一个 MCP server 注册到 Claude Code。你的 Claude Code 会话——跑在你自己的 Pro/Max 订阅上——成为 **Maestro(指挥者)**,一个由 Opus 驱动的编排者,负责拆解工作并通过 MCP 工具把它派发给团队其余成员。

```
┌──────────────────────────────────────────────────┐
│  Claude Code (Opus, 你的订阅)                     │
│  ↳ Maestro: 理解意图、规划、评审                  │
└──────────────────────────────────────────────────┘
                       ↓ MCP
┌──────────────────────────────────────────────────┐
│  Maestro Server (本地 Python 进程)                │
│  ↳ 把任务路由给合适的团队成员                     │
│  ↳ 运行质量门                                     │
│  ↳ 记录每一个决策以保证透明                       │
└──────────────────────────────────────────────────┘
        ↓             ↓             ↓             ↓
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ Coder       │ │ Librarian   │ │ Reviewer    │ │ Scribe      │
│             │ │             │ │             │ │             │
│ DeepSeek    │ │ DeepSeek    │ │ DeepSeek    │ │ DeepSeek    │
│ v4-pro      │ │ v4-flash    │ │ v4-pro      │ │ v4-flash    │
│             │ │             │ │             │ │             │
│ 按精确规格  │ │ 抽取与任务  │ │ 对照规格    │ │ 起草提交    │
│ 实现代码    │ │ 相关的上下文│ │ 评审代码    │ │ 和 PR 正文  │
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
```

指挥者从不缺席——每一次派发和每一个结果都流回 Opus,由它整合工作并做出下一个决策。你在自己平常的 Claude Code 会话里看到这一切。

---

## 团队

每个角色之所以存在,是因为它能做别人做不了、或做不了这么便宜的事。

### 🏛️ Architect(Opus,指挥者本身)

这就是你的 Claude Code 主会话。负责架构决策、横切关注点和最终整合。Architect 不写样板代码——它决定该有什么,并评审返回来的东西。

**始终在线**。这是你的交互界面。

### ⚙️ Coder(DeepSeek v4-pro)

按精确的规格说明实现代码。测试、校验器、CRUD 端点、数据类、脚手架、聚焦的重构。给它清晰的规格时,它快且出人意料地能干;提供这份规格,是 Architect 的职责。

**何时用**:规格具体、工作主要是机械性的。

### 📚 Librarian(DeepSeek v4-flash)

阅读长篇参考文档(设计文档、ADR、journal),抽取与查询相关的部分,并逐字引用硬约束。通过 `file_path` 路由文档,可以让它完全不进入编排者昂贵的上下文。

**何时用**:你本来要读一份 14 KB 的设计文档,只为找出三条约束。

### 🔍 Reviewer(DeepSeek v4-pro)

判断代码是否符合规格——pass / concerns / fail,附结构化的发现列表。这不是重构或风格评审;Reviewer 的职责是对规格的忠实度,而不是改进代码。

**何时用**:worker 代码到了,你需要第二意见来确认它是否满足需求。

### 📝 Scribe(DeepSeek v4-flash)

从 `git diff` 加 issue 正文起草提交信息和 PR 正文,遵循项目的 Conventional Commits + co-author 约定。从结构化输入做例行起草。

**何时用**:一个改动准备好提交,你本来要手敲提交信息。

---

## 质量门

便宜模型会犯错。Maestro 的职责是在你之前把它们抓出来。

- **结构化推理**:每个 worker 在输出之外,还返回它的推理过程和一个 "concerns" 段。指挥者能看到 worker 对哪些地方没把握。
- **测试驱动派发**:对于实现类任务,Architect 先写测试,再派发实现,然后自动跑测试。
- **自动评审**:Coder 的产出在整合前,由 Reviewer 对照其规格评审——合并前 reviewer pass 是强制的。
- **完整审计日志**:每一次派发、每一个响应、每一个 token 计数都记录到 `~/.maestro/logs/`。可直接查 JSONL,或在 Web UI 里浏览。

---

## 快速上手

### 1. 下载二进制

Maestro 以单文件原生二进制分发——无需 Python、无需 `pip`、无需虚拟环境。从[最新发布](https://github.com/kmeng/maestro/releases/latest)拿到你操作系统对应的产物:

| 操作系统                       | 产物                           |
| ----------------------------- | ------------------------------ |
| macOS (Apple Silicon)         | `maestro-macos-arm64.tar.gz`   |
| Linux x64                     | `maestro-linux-x64.tar.gz`     |
| Windows x64                   | `maestro-windows-x64.zip`      |

解压后把 `maestro` 放到 `PATH` 上的某个目录:

```bash
# macOS / Linux
tar -xzf maestro-macos-arm64.tar.gz
sudo mv maestro /usr/local/bin/

# Windows (PowerShell)
Expand-Archive maestro-windows-x64.zip
Move-Item maestro\maestro.exe "$env:USERPROFILE\bin\"
```

> **macOS 首次运行**:二进制目前未签名(代码签名在计划中)。macOS Gatekeeper 会提示*"无法验证开发者"*。绕过一次即可:在访达里右键 `maestro` → 打开 → 在对话框中点"打开"。之后正常运行。

### 2. 配置 API key

Maestro 从 `.env`(在你的项目根目录)或 shell 环境读取提供方凭据。最少需要 `DEEPSEEK_API_KEY` / `DASHSCOPE_API_KEY` / `ANTHROPIC_API_KEY` 之一:

```bash
# 项目根目录的 .env,或导出到 shell
DEEPSEEK_API_KEY=sk-...
```

在 [platform.deepseek.com](https://platform.deepseek.com) 获取 DeepSeek key;注册赠送的免费额度足够你起步。

角色到模型的映射有开箱即用的默认值(判断密集的角色用 DeepSeek v4-pro,抽取类用 v4-flash)。要按角色覆盖,在项目根目录放一个 `team.yaml`——schema 见[团队配置指南](docs/architecture.md)。

### 3. 注册到 Claude Code

```bash
maestro install
```

这会写入(或更新)`~/.claude/mcp.json`,加上一个指向该二进制的 `maestro` 条目。可用 flag:

- `--force` — 不提示直接覆盖已有的 maestro 条目
- `--dry-run` — 预览改动但不写入
- `--config-path <path>` — 覆盖目标路径(进阶 / 测试用)

### 4. 重启 Claude Code,然后验证

安装后,**重启 Claude Code** 让它加载新的 MCP server(为什么需要,见[升级指南](docs/ops/mcp-reload.md))。然后在任意 Claude Code 会话里运行:

```
/mcp
```

你应该看到 `maestro` 显示为 **connected**,带 6 个工具:`coder`、`librarian`、`reviewer`、`scribe`、`verifier`、`spec_writer`。

### 升级

有新版本时:下载新产物,替换 PATH 上的二进制,然后**重启 Claude Code**(MCP 工具列表按会话缓存——和首次安装同样的重载逻辑)。

### 使用

正常和 Claude Code 对话即可。Maestro 工具以 `mcp__maestro__*` 形式可用,指挥者会自动派发。想让委派更激进,在你项目的 `CLAUDE.md` 里放上:

```markdown
本项目使用 Maestro。把执行型工作委派给团队:
- 规格驱动的实现 → coder
- 长文档上下文抽取 → librarian
- 对照规格的代码评审 → reviewer
- 提交信息和 PR 正文 → scribe
- 把你自己的注意力留给架构、整合和评审。
```

---

## 你会看到什么

一次典型会话长这样:

```
你: 给一个健身追踪器做一套 REST API。用户可以记录锻炼、
    分享给好友、看到好友锻炼的动态流。

Architect(你,在 Claude Code 里):
  我先把需求理清楚。
  → 派发给 librarian,抽取规格里的硬约束……

  [Maestro: librarian (deepseek-v4-flash) — 2.4s, $0.001]
  返回 3 条硬约束 + 逐段摘要。

  审视这份规格……我会这样组织:users、workouts、follows、feed。
  先写数据模型和测试。

  [Architect 写 models.py 和 test_workouts.py — Opus]

  现在派发例行实现:
  → 派发给 coder(3 个端点,1 次派发)……

  [Maestro: coder (deepseek-v4-pro) — 6.1s, $0.002]
  返回 3 个端点处理函数。Concerns: "用了基础的鉴权检查;
  如需更细粒度的权限,建议复核。"

  跑测试……7/7 通过。审视那条鉴权 concern——对 v1 来说规格
  没问题,先搁置。起草提交:

  → 派发给 scribe……

  [Maestro: scribe (deepseek-v4-flash) — 2.8s, $0.001]
  返回提交信息 + PR 正文草稿。

  完成。合计:$0.004,11.3s。
  纯 Opus 跑法的估算:约 $0.18。
```

每一步都显示派发了什么、返回了什么、花了多少、指挥者如何就此推理。没有任何东西藏在黑箱里。

---

## 项目状态

Maestro 已过 MVP 阶段,被维护者日常使用。**v0.1.0 是最新发布版**(macOS / Linux / Windows 的单文件二进制);**v1.0 是当前的开发分支**。基础版(v0.0.3)交付了四个核心角色、结构化审计日志和自动评审质量门;v0.0.4 加上了 Web UI 驾驶舱和两个 shadow 模式角色(`verifier`、`spec_writer`)。

- ✅ 带 6 个 worker 工具的 MCP server——四个已转正(`coder`、`librarian`、`reviewer`、`scribe`)+ 两个 shadow 模式(`verifier`、`spec_writer`)
- ✅ DeepSeek(v4-pro / v4-flash)提供方;Anthropic + Qwen 可插拔
- ✅ 每个 worker 都返回结构化推理 + concerns
- ✅ 审计日志写入 JSONL + 按派发的成本遥测
- ✅ 自动评审质量门(合并前 reviewer pass 强制)
- ✅ Web UI 驾驶舱(`/`、`/team`、`/wizard`、`/scaffold`、`/live`、`/history`、`/savings`、`/problems`)
- ✅ 单文件二进制打包 + GitHub Releases 分发(macOS / Linux / Windows)

每个版本都记录在 [`docs/journal/`](./docs/journal/);带 worker 级成本遥测的 epic 收尾总结落在 [`docs/savings.md`](./docs/savings.md)。

---

## 设计原则

这些是我们做设计决策时遵循的规则。值得明说,因为它们正是 Maestro 区别于其他多智能体框架的地方。

1. **指挥者永远是前沿模型。** 便宜模型做路由决策比做代码还差。别想在编排者身上省钱。
2. **规格优于人设。** 一个"产品经理"角色之所以有价值,不是因为它假装成一个人——而是因为它产出结构化的规格。角色由其产出定义,而非职位头衔。
3. **默认透明。** 每一次派发都被记录。每个 worker 都解释它的推理。如果你说不出一段代码为什么长成那样,这个系统就失败了。
4. **质量门,而非盲目信任。** 便宜模型是工具,不是队友。它们像任何不可信输入一样被评审和测试。
5. **原生于 Claude Code,而非取代它。** Claude Code 已经把编排者体验(权限、diff、worktree)做对了。Maestro 扩展它,而不是与它竞争。

---

## 常见问题

**这违反 Anthropic 的服务条款吗?**
不违反。Maestro 通过标准 MCP 协议把 Claude Code 当作编排者——这正是 MCP 的设计目的。你的 Claude 订阅 token 从不离开 Claude Code 的进程。便宜模型的 API 调用是用你另外的 API key,从 Maestro 直接发给提供方。

**为什么用 MCP,而不是直接在 Python 脚本里调模型?**
因为 Claude Code 的 UI、权限系统、文件 diff、worktree 集成和对话记忆已经很出色。重造这一整套是个多年工程。MCP 让 Maestro 免费继承这一切。

**如果我想用 OpenAI / Gemini / 本地模型呢?**
任何带 OpenAI 兼容端点的提供方都开箱即用(包括 Ollama 这类本地服务)。在你的 `team.yaml` 里把 worker 的 `model:` 设成该提供方的 model ID——团队配置 schema 见 [`docs/architecture.md`](docs/architecture.md)。

**我能加自己的角色吗?**
能。角色由 YAML + 一个系统提示词模板定义。团队配置 schema 见 [`docs/architecture.md`](docs/architecture.md)。

**我怎么知道它真的省钱了?**
启动 Web UI(`maestro webui`),打开 **`/savings`** 页面——它显示每任务、每角色的成本,以及相对纯旗舰模型估算省了多少。同样的实测数据也在 [`docs/savings.md`](docs/savings.md)。

---

## 参与贡献

Maestro 正处在贡献者意见能塑造架构的阶段。如果你想帮忙:

- **在真实项目上用它一周**,然后开 issue 描述哪些好用、哪些不好用。这是当下最有价值的贡献。
- **加一个提供方**:任何带 OpenAI 兼容 API 的 LLM 提供方,大约 ~50 行代码。
- **提议一个角色**:开 issue 写清角色的用途、理想模型和示例派发。
- **改进质量门**:这是最难也最重要的问题。如果你有关于抓便宜模型错误的想法,我们很想听。

完整的贡献与工作流指南见 [`docs/governance.md`](docs/governance.md)。

---

## 许可证

MIT。随你怎么用。

---

## 致谢

Maestro 站在这些巨人的肩膀上:
- [Anthropic](https://anthropic.com)——Claude Code 和 MCP 协议
- [DeepSeek](https://deepseek.com)、[阿里 Qwen](https://qwen.ai),以及更广泛的开放模型生态,让低成本 AI 成为可能
- MetaGPT、ChatDev、CrewAI 等项目证明了多智能体编排可行——Maestro 从它们做对的和做错的地方学习
