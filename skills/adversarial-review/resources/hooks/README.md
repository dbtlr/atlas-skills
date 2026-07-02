# Enforcement hook — install

Optional hardening for Claude Code: a deterministic `PreToolUse` hook that blocks `gh pr create` when the branch carries no `Adversarial-Review:` trailer, making a forgotten gate structurally impossible rather than merely discouraged. The skill is complete without it — the trailer convention is the contract; this just enforces it.

Requires Python 3 and `git` on PATH. Stdlib only.

## Install (manual, one-time)

1. Locate the installed script and make it executable:

   ```bash
   chmod +x ~/.agents/skills/adversarial-review/resources/hooks/check-adversarial-review.py
   ```

   (Adjust the path to wherever the skill is installed — e.g. `~/.claude/skills/…` for a direct Claude Code install.)

2. Add the hook to your Claude Code settings (`~/.claude/settings.json` for all projects, or a repo's `.claude/settings.json` for just that repo), merging into any existing `hooks` block:

   ```json
   {
     "hooks": {
       "PreToolUse": [
         {
           "matcher": "Bash",
           "hooks": [
             {
               "type": "command",
               "command": "$HOME/.agents/skills/adversarial-review/resources/hooks/check-adversarial-review.py",
               "timeout": 10
             }
           ]
         }
       ]
     }
   }
   ```

3. Restart Claude Code — hooks load at session start and never hot-swap. Confirm with `/hooks`.

## What it does

On every Bash tool call it checks whether the command matches `gh pr create`. If so, it resolves the integration branch (`origin/HEAD`, with the same recovery ladder the skill documents) and greps `git log <base>..HEAD` for a line starting `Adversarial-Review: run` or `Adversarial-Review: skipped`. Found → the PR proceeds. Absent → exit 2 blocks the tool call and the stderr message tells the agent to run the adversarial-review skill first.

Deliberately fail-open in every state except the one it exists to catch (reviewable commits, no disposition): not a Bash call, not a PR creation, not a git repo, no resolvable base, no commits ahead — all allow. A gate that false-positives on weird repo shapes gets uninstalled; one that only fires on the real miss gets kept.

## Test it without creating a PR

```bash
HOOK=~/.agents/skills/adversarial-review/resources/hooks/check-adversarial-review.py
# from a branch with no trailer — expect exit 2 and the BLOCKED message:
echo '{"tool_name":"Bash","tool_input":{"command":"gh pr create"},"cwd":"'"$PWD"'"}' | "$HOOK"; echo "exit=$?"
# any non-PR command — expect exit 0, silence:
echo '{"tool_name":"Bash","tool_input":{"command":"git status"},"cwd":"'"$PWD"'"}' | "$HOOK"; echo "exit=$?"
```
