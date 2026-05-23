<div align="center">
<img src="maestro/webui/static/maestro-mark.svg" width="120" alt="Maestro">

# Maestro

**You conduct. The AI plays.** · Pay junior prices for senior-level output.

[![Release](https://img.shields.io/github/v/release/kmeng/maestro)](https://github.com/kmeng/maestro/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![Built with Claude Code](https://img.shields.io/badge/built%20with-Claude%20Code-d97757.svg)](https://claude.com/claude-code)
[![Self-built by AI](https://img.shields.io/badge/self--built%20by-AI-7c3aed.svg)](BUILD_LOG.md)

**English** | [中文](README.zh-CN.md)
</div>

> Orchestrate a heterogeneous AI software team. Pay junior prices for senior-level output.

Maestro is an open-source framework that turns Claude Code into the conductor of a complete AI software development team. Instead of burning top-tier model tokens on every task, Maestro routes work to the right specialist at the right cost — Opus for architecture; cheap models (DeepSeek v4-pro / v4-flash today, more providers pluggable) for implementation, document extraction, code review, and commit drafting.

The result: software development at roughly **10–20% the cost** of a pure flagship-model workflow, with quality gates that catch when the cheap models get it wrong.

> See [docs/savings.md](docs/savings.md) for the measured cost evidence backing this claim.

---

## Why Maestro

A real software team isn't ten senior architects. It's a few seniors directing a larger group of mid-level and junior engineers, each doing what they do best. AI coding tools today don't reflect this — they either burn flagship model tokens on every keystroke, or they downgrade everything to a cheaper model and lose quality.

Maestro takes the obvious next step: **heterogeneous models, role-matched, cost-aware**.

| | Pure Opus | Pure DeepSeek | **Maestro** |
|---|---|---|---|
| Cost | 💰💰💰💰💰 | 💰 | 💰💰 |
| Architecture quality | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| Boilerplate output | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Cross-file reasoning | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| You stay in control | ✅ | ⚠️ | ✅ |

---

## How it works

Maestro runs as an MCP server registered with Claude Code. Your Claude Code session — running on your Pro/Max subscription — becomes the **Maestro (conductor)**, an Opus-powered orchestrator that decomposes work and dispatches it to the rest of the team via MCP tools.

```
┌──────────────────────────────────────────────────┐
│  Claude Code (Opus, your subscription)           │
│  ↳ Maestro: understands intent, plans, reviews   │
└──────────────────────────────────────────────────┘
                       ↓ MCP
┌──────────────────────────────────────────────────┐
│  Maestro Server (local Python process)           │
│  ↳ Routes tasks to the right team member         │
│  ↳ Runs quality gates                            │
│  ↳ Logs every decision for transparency          │
└──────────────────────────────────────────────────┘
        ↓             ↓             ↓             ↓
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ Coder       │ │ Librarian   │ │ Reviewer    │ │ Scribe      │
│             │ │             │ │             │ │             │
│ DeepSeek    │ │ DeepSeek    │ │ DeepSeek    │ │ DeepSeek    │
│ v4-pro      │ │ v4-flash    │ │ v4-pro      │ │ v4-flash    │
│             │ │             │ │             │ │             │
│ Implements  │ │ Extracts    │ │ Reviews     │ │ Drafts      │
│ from a      │ │ task-       │ │ code        │ │ commits     │
│ precise     │ │ relevant    │ │ against     │ │ and PR      │
│ spec        │ │ context     │ │ a spec      │ │ bodies      │
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
```

The conductor never disappears — every dispatch and every result flows back through Opus, which integrates the work and makes the next decision. You see everything in your normal Claude Code session.

---

## The team

Each role exists because it does something the others can't do as well — or as cheaply.

### 🏛️ Architect (Opus, the conductor itself)

This is your Claude Code main session. Owns architectural decisions, cross-cutting concerns, and final integration. The Architect doesn't write boilerplate — it decides what should exist and reviews what comes back.

**Always on**. This is your interface.

### ⚙️ Coder (DeepSeek v4-pro)

Implements code from a precise specification. Tests, validators, CRUD endpoints, data classes, scaffolds, focused refactors. Fast and surprisingly competent when given a clear spec; the Architect's job is to provide one.

**Use when**: The spec is concrete and the work is mostly mechanical.

### 📚 Librarian (DeepSeek v4-flash)

Reads long reference documents (design docs, ADRs, journals) and extracts the parts relevant to a query, with hard constraints quoted verbatim. Routing the document via `file_path` keeps it out of the orchestrator's expensive context entirely.

**Use when**: You'd otherwise be reading a 14 KB design doc to find three constraints.

### 🔍 Reviewer (DeepSeek v4-pro)

Judges whether code matches a spec — pass / concerns / fail, with a structured findings list. Not a refactoring or style review; the Reviewer's job is fidelity to the spec, not improvement of the code.

**Use when**: Worker code arrived and you need a second opinion on whether it satisfies the requirements.

### 📝 Scribe (DeepSeek v4-flash)

Drafts commit messages and PR bodies from a `git diff` plus the issue body, following the project's Conventional Commits + co-author conventions. Routine drafting from structured input.

**Use when**: A change is ready to commit and you'd otherwise hand-type the message.

---

## Quality gates

Cheap models make mistakes. Maestro's job is to catch them before you do.

- **Structured reasoning**: Every worker returns its output alongside its reasoning and a "concerns" section. The conductor sees what the worker was uncertain about.
- **Test-driven dispatch**: For implementation tasks, the Architect writes tests first, dispatches the implementation, and runs the tests automatically.
- **Auto-review**: Coder output is reviewed by the Reviewer against its spec before integration — a reviewer pass is mandatory before merge.
- **Full audit log**: Every dispatch, every response, every token count is logged to `~/.maestro/logs/`. Query the JSONL directly, or browse it in the Web UI.

---

## Quick start

### 1. Download the binary

Maestro ships as a single-file native binary — no Python, no `pip`, no virtualenv. Grab the artifact for your OS from the [latest release](https://github.com/kmeng/maestro/releases/latest):

| OS                            | Artifact                       |
| ----------------------------- | ------------------------------ |
| macOS (Apple Silicon)         | `maestro-macos-arm64.tar.gz`   |
| Linux x64                     | `maestro-linux-x64.tar.gz`     |
| Windows x64                   | `maestro-windows-x64.zip`      |

Extract the archive and put `maestro` somewhere on your `PATH`:

```bash
# macOS / Linux
tar -xzf maestro-macos-arm64.tar.gz
sudo mv maestro /usr/local/bin/

# Windows (PowerShell)
Expand-Archive maestro-windows-x64.zip
Move-Item maestro\maestro.exe "$env:USERPROFILE\bin\"
```

> **macOS first run**: the binary is currently unsigned (code-signing is planned). macOS Gatekeeper will say *"developer cannot be verified"*. Bypass once: right-click `maestro` in Finder → Open → Open in the dialog. Future runs work normally.

### 2. Configure your API keys

Maestro reads provider credentials from `.env` (in your project root) or from your shell environment. The minimum is one of `DEEPSEEK_API_KEY` / `DASHSCOPE_API_KEY` / `ANTHROPIC_API_KEY`:

```bash
# .env in your project root, or export to your shell
DEEPSEEK_API_KEY=sk-...
```

Get a DeepSeek key at [platform.deepseek.com](https://platform.deepseek.com); the free signup credit is plenty to bootstrap with.

The role-to-model mapping has defaults that work out of the box (DeepSeek v4-pro for judgment-heavy roles, v4-flash for extraction). To override per-role, drop a `team.yaml` in your project root — see [the team config guide](docs/architecture.md) for the schema.

### 3. Register with Claude Code

```bash
maestro install
```

This writes (or updates) `~/.claude/mcp.json` with a `maestro` entry pointing at the binary. Flags:

- `--force` — overwrite an existing maestro entry without prompting
- `--dry-run` — preview the change without writing
- `--config-path <path>` — override the target (advanced / testing)

### 4. Restart Claude Code, then verify

After install, **restart Claude Code** so it picks up the new MCP server (see [the upgrade guide](docs/ops/mcp-reload.md) for why this is needed). Then in any Claude Code session run:

```
/mcp
```

You should see `maestro` listed as **connected** with 6 tools: `coder`, `librarian`, `reviewer`, `scribe`, `verifier`, `spec_writer`.

### Upgrading

When a new release comes out: download the new artifact, replace the binary on PATH, and **restart Claude Code** (the MCP tool-list is cached per session — same reload story as the first install).

### Use it

Just talk to Claude Code normally. Maestro tools are available as `mcp__maestro__*` and the conductor will dispatch automatically. To make delegation more aggressive, drop this in your project's `CLAUDE.md`:

```markdown
This project uses Maestro. Delegate execution-heavy work to the team:
- Spec-driven implementation → coder
- Long-doc context extraction → librarian
- Code review against spec → reviewer
- Commit messages and PR bodies → scribe
- Reserve your own attention for architecture, integration, and review.
```

---

## What you'll see

A typical session looks like this:

```
You: Build a REST API for a workout tracker. Users can log workouts,
     share them with friends, and see a feed of friends' workouts.

Architect (you, in Claude Code):
  Let me first get the requirements straight.
  → Dispatching to librarian to extract the spec hard constraints...

  [Maestro: librarian (deepseek-v4-flash) — 2.4s, $0.001]
  Returned 3 hard constraints + section-by-section summary.

  Reviewing the spec... I'll structure this as: users, workouts,
  follows, feed. Let me write the data model and tests first.

  [Architect writes models.py and test_workouts.py — Opus]

  Now dispatching the routine implementation:
  → Dispatching to coder (3 endpoints, 1 dispatch)...

  [Maestro: coder (deepseek-v4-pro) — 6.1s, $0.002]
  Returned 3 endpoint handlers. Concerns: "Used basic auth check;
  recommend reviewing if more granular permissions needed."

  Running tests... 7/7 pass. Reviewing the auth concern — the spec
  is fine for v1, deferring. Drafting the commit:

  → Dispatching to scribe...

  [Maestro: scribe (deepseek-v4-flash) — 2.8s, $0.001]
  Returned commit message + PR body draft.

  Done. Total: $0.004, 11.3s.
  Equivalent pure-Opus run estimate: ~$0.18.
```

Every step shows what was dispatched, what came back, what it cost, and how the conductor reasoned about it. Nothing is hidden in a black box.

---

## Project status

Maestro is past MVP and used daily by the maintainers. **v1.0.1 is the latest release** (single-file binaries for macOS / Linux / Windows). The foundation release (v0.0.3) shipped the four core roles, structured audit logging, and the auto-review quality gate; v0.0.4 added the Web UI cockpit and two shadow-mode roles (`verifier`, `spec_writer`); v1.0.0 added the CI quality gate and dashboard accuracy fixes (team-aware overview, applied-projects list, all-pages version display); v1.0.1 added the visual brand (logo + slogan), an About page (community feedback entry), and a README community section.

- ✅ MCP server with 6 worker tools — four promoted (`coder`, `librarian`, `reviewer`, `scribe`) + two shadow-mode (`verifier`, `spec_writer`)
- ✅ DeepSeek (v4-pro / v4-flash) providers; Anthropic + Qwen pluggable
- ✅ Structured reasoning + concerns from every worker
- ✅ Audit logging to JSONL + per-dispatch cost telemetry
- ✅ Auto-review quality gate (a reviewer pass is mandatory before merge)
- ✅ Web UI cockpit (`/`, `/team`, `/wizard`, `/scaffold`, `/live`, `/history`, `/savings`, `/problems`)
- ✅ Single-file binary packaging + GitHub Releases distribution (macOS / Linux / Windows)

Each release is documented in [`docs/journal/`](./docs/journal/); end-of-epic summaries with worker-level cost telemetry land in [`docs/savings.md`](./docs/savings.md).

---

## Design principles

These are the rules we use when making design decisions. They're worth stating because they're what makes Maestro different from other multi-agent frameworks.

1. **The conductor is always a frontier model.** Cheap models make worse routing decisions than they make code. Don't try to save money on the orchestrator.
2. **Specs over personas.** A "Product Manager" role isn't valuable because it pretends to be a person — it's valuable because it produces structured specs. Roles are defined by their outputs, not their job titles.
3. **Transparency by default.** Every dispatch is logged. Every worker explains its reasoning. If you can't tell why a piece of code came out the way it did, the system has failed.
4. **Quality gates, not blind trust.** Cheap models are tools, not teammates. They get reviewed and tested like any other untrusted input.
5. **Native to Claude Code, not a replacement for it.** Claude Code already nailed the orchestrator UX (permissions, diffs, worktrees). Maestro extends it; it doesn't compete with it.

---

## FAQ

**Is this against Anthropic's Terms of Service?**
No. Maestro uses Claude Code as its orchestrator via the standard MCP protocol — exactly what MCP was designed for. Your Claude subscription token never leaves Claude Code's process. The cheap-model API calls go directly from Maestro to the provider using your separate API keys.

**Why MCP instead of just calling models from a Python script?**
Because Claude Code's UI, permission system, file diffs, worktree integration, and conversation memory are already excellent. Reinventing that stack is a multi-year project. MCP lets Maestro inherit all of it for free.

**What if I want to use OpenAI / Gemini / local models?**
Any provider with an OpenAI-compatible endpoint works out of the box (this includes local servers like Ollama). Set the worker's `model:` in your `team.yaml` to the provider's model ID — see the team config schema in [`docs/architecture.md`](docs/architecture.md).

**Can I add my own roles?**
Yes. Roles are defined as YAML + a system-prompt template. See the team config schema in [`docs/architecture.md`](docs/architecture.md).

**How do I know it's actually saving money?**
Start the Web UI (`maestro webui`) and open the **`/savings`** page — it shows cost per task and per role, plus total saved versus a pure-flagship-model estimate. The same measured data lives in [`docs/savings.md`](docs/savings.md).

---

## Contributing

Maestro is in the phase where contributor input shapes the architecture. If you want to help:

- **Try it on a real project for a week**, then open an issue describing what worked and what didn't. This is the most valuable contribution right now.
- **Add a provider**: any LLM provider with an OpenAI-compatible API takes ~50 lines.
- **Propose a role**: open an issue with the role's purpose, ideal model, and example dispatches.
- **Improve quality gates**: this is the hardest and most important problem. If you have ideas about catching cheap-model errors, we want to hear them.

See [`docs/governance.md`](docs/governance.md) for the full contribution and workflow guide.

---

## Community / Contact

Maestro is built and maintained by **挖宝的瓦力**. Follow along, get help, or share feedback:

<table><tr>
<td align="center"><b>WeChat Official Account</b><br>
<img src="maestro/webui/static/qr-wechat-mp.jpg" width="180"><br>Methodology &amp; updates</td>
<td align="center"><b>WeChat (personal)</b><br>
<img src="maestro/webui/static/qr-wechat-personal.jpg" width="180"><br>Add me for direct feedback</td>
<td align="center"><b>GitHub</b><br>
<a href="https://github.com/kmeng/maestro/issues">Issues</a> · Star ⭐<br>Bugs, ideas, contributions</td>
</tr></table>

---

## License

MIT. Use it however you want.

---

## Credits

Maestro stands on the shoulders of:
- [Anthropic](https://anthropic.com) for Claude Code and the MCP protocol
- [DeepSeek](https://deepseek.com), [Alibaba Qwen](https://qwen.ai), and the broader open-model ecosystem for making cost-effective AI possible
- The MetaGPT, ChatDev, and CrewAI projects for proving multi-agent orchestration works — Maestro learns from what they got right and what they got wrong
