# Maestro Bootstrap — Quick Start

This is the v0.0.1 hand-written bootstrap. From v0.0.2 onward, Maestro will be
extended using itself.

## What's here

- **`maestro_server.py`** — A single-file MCP server exposing one tool: `cheap_code_gen`. Routes to DeepSeek-Coder.
- **`requirements.txt`** — Python deps.
- **`../.env.example`** (at repo root) — template for your local `.env` config.

## Setup (5 minutes)

### 1. Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate    # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure your API key

Go to https://platform.deepseek.com → API Keys → create a new key. They give a few free dollars on signup, plenty to bootstrap with.

Then, from the repo root, create your local `.env`:

```bash
cp .env.example .env
```

Open `.env` in your editor and fill in the key:

```
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxx
```

`.env` is at the **repo root** (not inside `bootstrap/`). It is gitignored — your real key never leaves your machine, and is never read by your shell or any MCP client config.

### 3. Test the server runs

```bash
python bootstrap/maestro_server.py
```

The server reads `.env` on startup, then sits silently waiting for MCP messages on stdio. Press `Ctrl+C` to exit.

If something is wrong (missing key, malformed `.env`), the server prints an actionable error pointing at the exact file and line you need to fix — read it carefully before continuing.

### 4a. Register with Claude Code

```bash
claude mcp add maestro -- /absolute/path/to/.venv/bin/python /absolute/path/to/bootstrap/maestro_server.py
```

Use `pwd` to get absolute paths if unsure. **No `--env` flag is needed** — the server self-loads `DEEPSEEK_API_KEY` from `.env`. The MCP client never sees the key.

### 4b. (Alternative) Register with Claude Desktop

Edit your Claude Desktop config (macOS path shown — adjust for your OS):

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

Add an `mcpServers.maestro` entry. If the file already has `mcpServers`, just add the `maestro` key alongside existing entries:

```json
{
  "mcpServers": {
    "maestro": {
      "command": "/absolute/path/to/.venv/bin/python",
      "args": ["/absolute/path/to/bootstrap/maestro_server.py"]
    }
  }
}
```

**No `env` block needed** — same reason as Claude Code. The server reads its key from `.env`.

After saving the config, **fully quit Claude Desktop and restart it** (Cmd+Q on macOS, not just close the window) so it re-reads the config.

### 5. Verify in your client

In Claude Code, run `/mcp` — you should see `maestro` listed as connected, with one tool: `cheap_code_gen`.

In Claude Desktop, the running tools are visible in the conversation UI; ask "what tools do you have?" or look at the tool icon, and you should see `cheap_code_gen` available.

## First test dispatch

In your client, try this prompt:

```
Use the maestro cheap_code_gen tool to generate a Python function
that takes a list of integers and returns a dict mapping each integer
to its square.
```

The orchestrating model should call the tool. You'll see:
- The dispatch line: `[junior_engineer dispatch — deepseek-coder — 2.4s — 187 tokens]`
- A `<reasoning>` block explaining what DeepSeek understood
- An `<output>` block with the actual code
- A `<concerns>` block (probably "none" for something this simple)

Then check the log:

```bash
cat ~/.maestro/logs/$(date +%Y-%m-%d).jsonl | tail -1 | python -m json.tool
```

You should see the full record: input, output, tokens, duration.

## If it doesn't work

**Server shows as failed/disconnected (Claude Code `/mcp`, or Claude Desktop tool list):**
- Most common cause: `.env` is missing, or `DEEPSEEK_API_KEY` in `.env` is empty. Reproduce what your MCP client sees by running the server with empty environment and reading the error:
  ```bash
  env -i HOME="$HOME" PATH="$PATH" /absolute/path/to/.venv/bin/python /absolute/path/to/bootstrap/maestro_server.py
  ```
  The error message tells you the exact file path and line to add.
- Verify the absolute paths in your registration command (Claude Code) or `claude_desktop_config.json` (Desktop) point at real files. Use `pwd` from inside the repo to get the right paths.
- Make sure `.env` is at the **repo root** (the same level as `README.md`), not inside `bootstrap/`. The server only looks at the repo root.
- For Claude Desktop, remember to fully quit (Cmd+Q on macOS) and restart after editing the config — closing the window alone does not re-read it.

**Tool runs but returns an API error:**
- Check your DeepSeek balance at platform.deepseek.com
- Verify the key in `.env` is correct: `grep DEEPSEEK_API_KEY .env` (from repo root)

**Orchestrating model doesn't call the tool:**
- This is normal at first. Try being explicit: "Use the cheap_code_gen tool to..."
- Once it works once, it tends to use the tool more readily for similar tasks
- Tweak the tool description in `maestro_server.py` if it consistently ignores it

## What to do once it works

This is the moment Maestro becomes self-hosting. Your next feature should be developed using Maestro itself:

1. Pick the next tool to add (suggested: `cheap_explain` for summarization)
2. In your client, prompt the orchestrating model to design it
3. Have the orchestrator call `cheap_code_gen` to write the implementation
4. Review, integrate, test
5. **Commit with AI authorship attribution** — see `BUILD_LOG.md` template

Welcome to dogfooding recursion.
