# Post-create nudge hook — install

Optional hardening for Claude Code: a `PostToolUse` hook that, after a `gh pr create` succeeds, nudges the agent to arm `watching-a-pr` on the new PR. It's the **backstop** for a PR opened *outside* the `finishing-a-task` flow (which already hands off to the watcher) — it makes sure a directly-created PR still gets watched.

It only nudges (injects a `systemMessage`); it can't launch the watcher itself — a hook-spawned process isn't harness-tracked to re-invoke the agent, so only a watcher the agent launches carries that wiring.

Requires Python 3. Stdlib only.

## Install (manual, one-time)

1. Make it executable:

   ```bash
   chmod +x ~/.agents/skills/watching-a-pr/resources/hooks/nudge-watch-pr.py
   ```

   (Adjust the path to wherever the skill is installed.)

2. Add a `PostToolUse` entry to your Claude Code settings (`~/.claude/settings.json`), merging into any existing `hooks` block. Use the **`if` field** to scope it to `gh` commands, so the script only spawns on GitHub calls:

   ```json
   {
     "hooks": {
       "PostToolUse": [
         {
           "matcher": "Bash",
           "hooks": [
             {
               "type": "command",
               "if": "Bash(gh *)",
               "command": "~/.claude/hooks/nudge-watch-pr.py"
             }
           ]
         }
       ]
     }
   }
   ```

   (`if: "Bash(gh *)"` fires the hook only when a `gh` command runs — it strips leading `VAR=value` and inspects subcommands in compound commands — so the Python isn't spawned on every Bash call.)

3. Restart Claude Code — hooks load at session start. Confirm with `/hooks`.

## What it does

On a Bash `gh … pr … create` (flags may interleave) whose output contains a PR URL (`https://github.com/…/pull/<N>`), it emits a `systemMessage` telling the agent to invoke `watching-a-pr` with PR #N. On anything else — not a PR creation, a creation that produced no URL (i.e. failed), an unparseable command — it emits nothing. Fail-open throughout: a missed nudge just means the agent arms the watcher itself; a spurious one would be noise, so it fires only on a confirmed creation.

## Test without creating a PR

```bash
H=~/.claude/hooks/nudge-watch-pr.py
echo '{"tool_name":"Bash","tool_input":{"command":"gh pr create -f"},"tool_result":"https://github.com/o/r/pull/42"}' | "$H"; echo "exit=$?"
echo '{"tool_name":"Bash","tool_input":{"command":"gh pr view 42"},"tool_result":"..."}' | "$H"; echo "(should be silent) exit=$?"
```
