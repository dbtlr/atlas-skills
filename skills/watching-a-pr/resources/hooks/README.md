# Post-create nudge hook — install

Optional hardening for Claude Code: a `PostToolUse` hook that, after a `gh pr create` succeeds, nudges the agent to arm `watching-a-pr` on the new PR. It makes sure a directly-created PR gets watched even when no workflow handed it off to the watcher.

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
               "command": "$HOME/.agents/skills/watching-a-pr/resources/hooks/nudge-watch-pr.py"
             }
           ]
         }
       ]
     }
   }
   ```

   Use the **same path** you chmod'd in step 1 (adjust it to your install location). The **`if: "Bash(gh *)"`** (Claude Code **v2.1.85+**) fires the hook only when a `gh` command runs — it strips leading `VAR=value` and inspects subcommands in compound commands — so the Python isn't spawned on every Bash call. It matches by command *name*, so an absolute-path invocation (`/opt/homebrew/bin/gh …`) would skip it; the nudge is low-stakes, so that's an acceptable miss. Omit `if` on builds older than v2.1.85 — the script self-filters either way.

3. Restart Claude Code — hooks load at session start. Confirm with `/hooks`.

## What it does

On a Bash PR creation — `gh … pr … create` (flags may interleave) or `gh api …/pulls` — whose `tool_output` contains a PR URL (`https://<host>/…/pull/<N>`, any GitHub host), it emits a `systemMessage` telling the agent to invoke `watching-a-pr` with PR #N. It reads the **last** URL in the output (the one `gh` prints for the created PR, not one referenced in the command body) and doesn't assert "created" — a re-run on an existing PR still correctly points at a PR worth watching. On anything else — not a PR creation, no URL in the output (a failed create), an unparseable command, or an unexpected payload shape — it emits nothing. **Fail-open throughout, unconditionally**: the whole body is guarded, so no payload can make it crash the tool call.

## Test without creating a PR

```bash
H=~/.agents/skills/watching-a-pr/resources/hooks/nudge-watch-pr.py
echo '{"tool_name":"Bash","tool_input":{"command":"gh pr create -f"},"tool_output":"https://github.com/o/r/pull/42"}' | "$H"; echo "exit=$?"
echo '{"tool_name":"Bash","tool_input":{"command":"gh pr view 42"},"tool_output":"..."}' | "$H"; echo "(should be silent) exit=$?"
```
