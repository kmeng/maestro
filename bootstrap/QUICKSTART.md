# Maestro Bootstrap — Quick Start

This is the v0.0.1 hand-written bootstrap. From v0.0.2 onward, Maestro will be
extended using itself.

## What's here

- **`maestro_server.py`** — A single-file MCP server exposing one tool: `cheap_code_gen`. Routes to DeepSeek-Coder.
- **`requirements.txt`** — Python deps.

## Setup (5 minutes)

### 1. Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate    # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Get a DeepSeek API key

Go to https://platform.deepseek.com → API Keys → create a new key. They give a few free dollars on signup, plenty to bootstrap with.

```bash
export DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxx
```

(Add to your `~/.zshrc` or `~/.bashrc` so you don't have to redo it every shell.)

### 3. Test the server runs

```bash
python maestro_server.py
```

It should sit there silently waiting for MCP messages on stdio. Press `Ctrl+C` to exit. If you see an error, fix it before continuing.

### 4. Register with Claude Code

```bash
claude mcp add maestro -- python /absolute/path/to/maestro_server.py
```

Replace `/absolute/path/to/` with the real path. Use `pwd` if unsure.

If you're using a venv, point at the venv's python:

```bash
claude mcp add maestro -- /absolute/path/to/.venv/bin/python /absolute/path/to/maestro_server.py
```

### 5. Verify in Claude Code

Start Claude Code, then:

```
/mcp
```

You should see `maestro` listed as connected, with one tool: `cheap_code_gen`.

## First test dispatch

In Claude Code, try this prompt:

```
Use the maestro cheap_code_gen tool to generate a Python function
that takes a list of integers and returns a dict mapping each integer
to its square.
```

Claude Opus should call the tool. You'll see:
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

**`/mcp` shows maestro as failed/disconnected:**
- Check the absolute path in `claude mcp add` is correct
- Try running `python /absolute/path/to/maestro_server.py` manually — any error will show
- Make sure `DEEPSEEK_API_KEY` is exported in the same shell where you start Claude Code (or set it in the `claude mcp add` command with `--env`)

**Tool runs but returns an API error:**
- Check your DeepSeek balance at platform.deepseek.com
- Try a simpler test: `curl https://api.deepseek.com/v1/models -H "Authorization: Bearer $DEEPSEEK_API_KEY"`

**Opus doesn't call the tool:**
- This is normal at first. Try being explicit: "Use the cheap_code_gen tool to..."
- Once it works once, it tends to use it more readily for similar tasks
- Tweak the tool description in `maestro_server.py` if it consistently ignores it

## What to do once it works

This is the moment Maestro becomes self-hosting. Your next feature should be developed using Maestro itself:

1. Pick the next tool to add (suggested: `cheap_explain` for summarization)
2. In Claude Code, prompt Opus to design it
3. Have Opus call `cheap_code_gen` to write the implementation
4. Review, integrate, test
5. **Commit with AI authorship attribution** — see `BUILD_LOG.md` template

Welcome to dogfooding recursion.
