# Reloading Maestro after install or upgrade

> Short version: after installing or upgrading Maestro, **restart Claude
> Code** (or reset its MCP connection) before the new tools become
> visible to the session.

## Symptom

You upgraded Maestro (`pip install -U maestro-mcp`), or you added a new
worker role, or you changed a tool's input schema — but in your current
Claude Code session:

- `/mcp` still shows the old tool list
- The model says it does not have a tool that you know was just added
- A tool call fails with `InputValidationError` against a schema you
  thought was fixed in the upgrade

This is not a Maestro bug. It is how Claude Code handles MCP server
connections.

## Cause

Claude Code negotiates the list of MCP tools (`tools/list`) and their
JSON schemas **once per session**, when the MCP server first connects.
The result is cached for the lifetime of that session. Restarting the
Maestro process alone is not enough — Claude Code has to re-issue
`tools/list` against the new process. That happens when:

- Claude Code itself is restarted, or
- The MCP server connection is explicitly reset from inside Claude Code

Until one of those happens, the in-flight session keeps using the
schema and tool list it cached at session start.

## When you need to reload

| Action | Reload required? |
|---|---|
| First-time `pip install maestro-mcp` + `maestro install` | Yes — restart Claude Code so it picks up the new `~/.claude/mcp.json` entry |
| Upgrade Maestro version (`pip install -U maestro-mcp`) | Yes — Claude Code is still talking to the old binary's tool list |
| Add or remove a worker role | Yes — the role appears / disappears from `tools/list` |
| Change a worker's input or output schema | Yes — Claude Code keeps the old schema and rejects calls that match the new one |
| Edit `~/.maestro/config.yaml` (models, providers, gates) | **No** — config is read per-dispatch, no schema change |
| Edit a worker's system prompt | **No** — prompts are read per-dispatch |
| Local development: edit Maestro source under an editable install | Yes if you changed the tool schema or the role list; otherwise no |

## How to reload

### Option 1: Restart Claude Code (always works)

Quit Claude Code, reopen the project, run `/mcp` to confirm `maestro`
is listed as `connected`. The new tool list is now active.

### Option 2: Reset only the MCP connection (if your Claude Code build supports it)

Newer Claude Code builds support resetting an individual MCP server
without restarting the whole client. Check `/mcp` for a reload action,
or consult Claude Code's docs for your installed version. If you cannot
find it, fall back to Option 1.

## Verifying the reload worked

```text
/mcp
```

You should see `maestro` listed as `connected`, with the expected tool
count. As of v0.0.4 Maestro ships **6 worker tools**:

- `coder`
- `librarian`
- `reviewer`
- `scribe`
- `verifier`
- `spec-writer`

If the count or names do not match, the reload did not take effect —
restart Claude Code (Option 1).

## Local development tip

If you are iterating on Maestro itself with an editable install
(`pip install -e .`), every change to a tool's schema or a new role
registration requires a Claude Code restart before you can test the
change end-to-end from a real session. Plan dev cycles around that:
batch schema work so you reload once, not on every edit.
