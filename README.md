# Maestro

> Orchestrate a heterogeneous AI software team. Pay junior prices for senior-level output.

Maestro is an open-source framework that turns Claude Code into the conductor of a complete AI software development team. Instead of burning top-tier model tokens on every task, Maestro routes work to the right specialist at the right cost — Opus for architecture, Sonnet for complex implementation, DeepSeek for boilerplate, Qwen for documentation.

The result: software development at roughly **10–20% the cost** of a pure flagship-model workflow, with quality gates that catch when the cheap models get it wrong.

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
│ Product     │ │ Senior      │ │ Junior      │ │ Documentar- │
│ Manager     │ │ Engineer    │ │ Engineer    │ │ ian         │
│             │ │             │ │             │ │             │
│ Sonnet      │ │ Sonnet      │ │ DeepSeek    │ │ Qwen        │
│             │ │             │ │ -Coder      │ │             │
│ Translates  │ │ Complex     │ │ Boilerplate │ │ Docs,       │
│ business    │ │ logic,      │ │ CRUD,       │ │ comments,   │
│ goals into  │ │ debugging,  │ │ scaffolds,  │ │ summaries,  │
│ specs       │ │ reviews     │ │ tests       │ │ explanations│
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
```

The conductor never disappears — every dispatch and every result flows back through Opus, which integrates the work and makes the next decision. You see everything in your normal Claude Code session.

---

## The team

Each role exists because it does something the others can't do as well — or as cheaply.

### 🎯 Product Manager (Sonnet)

Translates fuzzy business goals into concrete product specifications. When you say "I want users to be able to share workouts with friends," the PM produces user stories, acceptance criteria, edge cases, and the data model implications — before a single line of code gets written.

**Use when**: You start with intent, not specs. Requirements need stakeholder framing. You're not sure what to build yet.

### 🏛️ Architect (Opus, the conductor itself)

This is your Claude Code main session. Owns architectural decisions, cross-cutting concerns, and final integration. The Architect doesn't write boilerplate — it decides what should exist and reviews what comes back.

**Always on**. This is your interface.

### 🛠️ Senior Engineer (Sonnet)

Handles complex implementation that requires understanding context across files: tricky refactors, debugging, code review, security-sensitive logic.

**Use when**: The task requires reasoning, not just execution.

### ⚙️ Junior Engineer (DeepSeek-Coder)

Cranks out well-specified code: CRUD endpoints, data classes, config files, standard React components, simple algorithms. Fast, cheap, surprisingly competent when given a clear spec.

**Use when**: The spec is precise and the work is mostly mechanical.

### 📝 Documentarian (Qwen)

Writes docstrings, READMEs, API docs, code comments, and plain-language summaries of long logs or files.

**Use when**: The output is prose, not code.

---

## Quality gates

Cheap models make mistakes. Maestro's job is to catch them before you do.

- **Structured reasoning**: Every worker returns its output alongside its reasoning and a "concerns" section. The conductor sees what the worker was uncertain about.
- **Test-driven dispatch**: For implementation tasks, the Architect writes tests first, dispatches the implementation, and runs the tests automatically.
- **Auto-review**: Junior Engineer output above a complexity threshold is reviewed by Senior Engineer before integration.
- **Confidence escalation**: If a worker reports low confidence, the task is automatically retried by a stronger model.
- **Full audit log**: Every dispatch, every response, every token count is logged to `~/.maestro/logs/`. Inspect with `maestro logs` or query the JSONL directly.

---

## Quick start

### Install

```bash
pip install maestro-mcp
```

### Configure

Create a config file at `~/.maestro/config.yaml`:

```yaml
providers:
  deepseek:
    api_key: ${DEEPSEEK_API_KEY}
    base_url: https://api.deepseek.com/v1
  qwen:
    api_key: ${DASHSCOPE_API_KEY}
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
  anthropic:
    api_key: ${ANTHROPIC_API_KEY}  # for Sonnet workers (optional)

team:
  product_manager:
    provider: anthropic
    model: claude-sonnet-4-6
  senior_engineer:
    provider: anthropic
    model: claude-sonnet-4-6
  junior_engineer:
    provider: deepseek
    model: deepseek-coder
  documentarian:
    provider: qwen
    model: qwen-plus

quality_gates:
  auto_review_threshold_loc: 50
  test_driven_implementation: true
  confidence_escalation: true
```

### Register with Claude Code

```bash
maestro install
```

This adds Maestro to your `~/.claude/mcp.json`. Restart Claude Code; you should see `maestro` connected when you run `/mcp`.

### Use it

Just talk to Claude Code normally. Maestro tools are available as `mcp__maestro__*` and the conductor will dispatch automatically. To make delegation more aggressive, drop this in your project's `CLAUDE.md`:

```markdown
This project uses Maestro. Delegate execution-heavy work to the team:
- Specs and user stories → @product_manager
- Boilerplate, scaffolds, tests → @junior_engineer
- Documentation → @documentarian
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
  → Dispatching to product_manager...

  [Maestro: product_manager (sonnet) — 4.2s, $0.008]
  Returned 3 user stories, 7 acceptance criteria, data model sketch.

  Reviewing the spec... I'll structure this as: users, workouts,
  follows, feed. Let me write the data model and tests first.

  [Architect writes models.py and test_workouts.py — Opus]

  Now dispatching the routine implementation:
  → Dispatching to junior_engineer (3 endpoints)...

  [Maestro: junior_engineer (deepseek) — 6.1s, $0.002]
  Returned 3 endpoint handlers. Concerns: "Used basic auth check;
  recommend reviewing if more granular permissions needed."

  Running tests... 7/7 pass. Reviewing the auth concern — the spec
  is fine for v1, deferring. Now generating docs:

  → Dispatching to documentarian...

  [Maestro: documentarian (qwen) — 2.8s, $0.001]
  Returned OpenAPI annotations and README section.

  Done. Total: $0.011, 13.1s.
  Equivalent pure-Opus run estimate: ~$0.18.
```

Every step shows what was dispatched, what came back, what it cost, and how the conductor reasoned about it. Nothing is hidden in a black box.

---

## Project status

Maestro is in early development. The MVP (Phase 1) is functional and used daily by the maintainers; production-readiness and broader provider support are in progress.

- ✅ MCP server with 4 core roles
- ✅ DeepSeek, Qwen, Anthropic providers
- ✅ Structured reasoning + concerns from every worker
- ✅ Audit logging to JSONL
- 🔄 Test-driven dispatch (in progress)
- 🔄 Auto-review quality gate (in progress)
- 📋 Confidence escalation
- 📋 Cost dashboard CLI (`maestro stats`)
- 📋 Local model support via Ollama
- 📋 Role marketplace (community-contributed roles)
- 📋 Benchmarks against SWE-bench subset

See the [roadmap](./ROADMAP.md) for details.

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
Any provider with an OpenAI-compatible endpoint works out of the box. Add it to `config.yaml`. Provider-specific quirks (Gemini's safety settings, Ollama's local serving) are documented in `docs/providers.md`.

**Can I add my own roles?**
Yes. Roles are defined as YAML + a system prompt template. See `docs/custom-roles.md`. Sharing role configs with the community is encouraged — eventually we want a role marketplace.

**How do I know it's actually saving money?**
Run `maestro stats` after a week. It shows cost per task by role, total saved versus a pure-flagship-model estimate, and which roles you actually used.

---

## Contributing

Maestro is in the phase where contributor input shapes the architecture. If you want to help:

- **Try it on a real project for a week**, then open an issue describing what worked and what didn't. This is the most valuable contribution right now.
- **Add a provider**: any LLM provider with an OpenAI-compatible API takes ~50 lines.
- **Propose a role**: open an issue with the role's purpose, ideal model, and example dispatches.
- **Improve quality gates**: this is the hardest and most important problem. If you have ideas about catching cheap-model errors, we want to hear them.

See `CONTRIBUTING.md` for the full guide.

---

## License

MIT. Use it however you want.

---

## Credits

Maestro stands on the shoulders of:
- [Anthropic](https://anthropic.com) for Claude Code and the MCP protocol
- [DeepSeek](https://deepseek.com), [Alibaba Qwen](https://qwen.ai), and the broader open-model ecosystem for making cost-effective AI possible
- The MetaGPT, ChatDev, and CrewAI projects for proving multi-agent orchestration works — Maestro learns from what they got right and what they got wrong
