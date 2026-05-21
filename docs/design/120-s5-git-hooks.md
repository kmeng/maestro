# Design: S5 enforcement for irreversible git ops

**Status**: draft (awaiting approval)
**Issue**: #120
**Related**: `feedback_branch_workflow` (S4, pending S5), `feedback_github_approval`, CODE-2026-05-19-002 § II.6, ADR — none (no long-term storage/interface change; this is local tooling)

## Problem

Memory rules are a single-layer defense gated on Claude actively recalling and applying them at the right moment (the "relevance judgment" single point of failure). For reversible ops this is fine — drift is cheap to undo. For **irreversible** ops (force-push, deleting unmerged branches, `rm -rf` on tracked paths, issue deletion) one missed recall can mean unrecoverable loss.

Defense strength should match violation-cost × irreversibility. Irreversible ops warrant **S5 enforcement**: a `PreToolUse` hook that fires at the harness level regardless of whether Claude remembered the rule.

Today these ops rely only on the auto-mode classifier + memory `feedback_github_approval` — there is no deterministic hook.

## Functional design (what Claude / the user experiences)

When Claude issues a Bash command that matches an irreversible-op pattern:

- **`deny` ops** (almost never legitimate without explicit human intent): the hook returns `permissionDecision: "deny"` with a reason. Claude sees the block, cannot proceed, and must surface it to the user — who can then run the command themselves or explicitly instruct.
- **`ask` ops** (legitimate sometimes, but must be deliberate): the hook returns `permissionDecision: "ask"`, triggering the normal user permission dialog. The user approves or rejects per-instance.
- **Everything else**: the hook returns nothing / allows; normal git usage is completely unaffected.

The hook is **silent on the happy path** — it only speaks when a dangerous pattern matches. No friction on the 99% of Bash calls that are safe.

## Technical design

### Registration

User-global, in `~/.claude/settings.json` (applies across all the user's projects — drift prevention is not project-specific):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "~/.claude/hooks/guard-irreversible-git.sh" }
        ]
      }
    ]
  }
}
```

`matcher` filters by tool name only (`"Bash"`). **All per-command logic lives in the script** — the matcher cannot pattern-match the command itself.

### Input contract

The hook receives JSON on stdin. Relevant fields:

```json
{
  "tool_name": "Bash",
  "tool_input": { "command": "git push --force origin main", "description": "..." },
  "cwd": "/path/to/project",
  "permission_mode": "default"
}
```

The script extracts the command with `jq -r '.tool_input.command'`.

### Decision output

Current (non-deprecated) format on stdout with exit 0:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "force-push blocked by guard-irreversible-git — run manually if intended"
  }
}
```

`permissionDecision` ∈ `allow` / `deny` / `ask`. For non-matching commands the script exits 0 with **no JSON** (falls through to normal permission flow). Exit 2 is the alternative hard-block path (stderr → Claude) but we prefer the JSON `deny` form because `permissionDecisionReason` surfaces cleanly in the UI.

### Gated operations + match patterns

The script matches against the extracted command string. Patterns are conservative (anchored to reduce false positives):

| Op | Pattern (regex, illustrative) | Decision | Rationale |
| --- | --- | --- | --- |
| Force push | `git push.*(--force\|-f)\b` (excluding `--force-with-lease`) | `deny` | Overwrites remote history; the prime irreversible git op |
| Delete remote branch | `git push\b.*--delete` / `git push\b.*:[^ ]` | `ask` | Legitimate cleanup (today's PR branches), but should be deliberate |
| Force delete local branch | `git branch\s+-D\b` | `ask` | `-D` deletes unmerged work; `-d` (safe) unaffected |
| Hard reset | `git reset\s+--hard\b` | `ask` | Discards uncommitted work |
| Recursive force remove | `rm\s+-rf?\b` / `rm\s+-fr?\b` | `ask` | Filesystem loss; too common to `deny`, must confirm |
| Issue/PR deletion | `gh issue delete\b` / `gh pr delete\b` | `deny` | External irreversible state |

`--force-with-lease` is explicitly **allowed** (it's the safe force-push variant).

### Composition with the auto-mode classifier

The hook fires **before** the auto-mode classifier. Layering:

1. **Hook (S5, deterministic)** — pattern match, fast, no LLM. Catches the enumerated ops every time.
2. **Auto-mode classifier (existing, probabilistic)** — LLM judgment on remaining cases.
3. **Memory `feedback_github_approval` (S4)** — Claude's own recall.

The hook does not replace the classifier; it adds a deterministic floor under it for the specific irreversible ops. A `deny` from the hook short-circuits; an `ask` defers to the normal permission dialog (which the classifier/permission settings still inform).

## False-positive avoidance

- Patterns anchored with `\b` word boundaries; `--force-with-lease` whitelisted; safe `-d` branch delete not matched.
- The script must be **fast** (fires on every Bash call): single `jq` extract + a `case`/grep chain, no subprocess fan-out, no network.
- Substring traps: `git push --delete` matching must not catch `--dry-run --delete`-style composite — test against a fixture corpus of safe commands before enabling.
- The script should fail **open** on its own errors (malformed input, jq missing) — exit 0 / allow — so a broken guard never bricks all Bash usage. (Trade-off: a broken guard silently stops guarding; acceptable because the memory + classifier layers remain.)

## Failure modes

| Failure | Effect | Mitigation |
| --- | --- | --- |
| Script bug rejects safe commands | Bash friction / blocked work | Fail-open on script error; fixture corpus test |
| Pattern misses a real dangerous op | Op proceeds (back to S4 defense) | Patterns are a floor not a ceiling; memory still applies |
| Hook timeout (fires every Bash call) | Slow tool calls | Keep script O(1), no subprocess fan-out |
| `jq` not installed | Script can't parse input | Fail-open + document `jq` as a prerequisite |

## Open implementation questions

1. Confirm the exact `permissionDecision` schema against the installed Claude Code version at implementation time (the API has evolved; `defer` may or may not be available).
2. Decide `deny` vs `ask` split — the table above is a proposal; force-push and external-delete as `deny`, local-destructive as `ask`. Open to tuning.
3. Whether to also gate `git commit --no-verify` / `--no-gpg-sign` (CLAUDE.md forbids these) — could fold into the same script as `ask`.

## Acceptance mapping (issue #120)

- "Design doc written + approved" → this doc
- "PreToolUse hook implemented in settings.json" → registration + script above
- "Trial run: gated ops trigger, non-gated unaffected" → fixture corpus test in implementation
- "Memory `feedback_branch_workflow` S4 → S5 once push/branch-delete hook lands" → upgrade after trial passes
- "Memory `feedback_github_approval` cross-references the hook" → memory edit at implementation
