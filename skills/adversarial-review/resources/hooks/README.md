# Enforcement hook — install

Optional hardening for Claude Code: a deterministic `PreToolUse` hook that blocks `gh pr create` when the branch carries no `Adversarial-Review:` trailer. It's a **speed bump for the forgotten gate, not a security boundary** — it catches the ordinary case (an agent about to open a PR without having run the review), not an agent determined to evade it. The skill is complete without it — the trailer convention is the contract; this just makes the common miss loud.

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
               "if": "Bash(gh *)",
               "command": "$HOME/.agents/skills/adversarial-review/resources/hooks/check-adversarial-review.py",
               "timeout": 10
             }
           ]
         }
       ]
     }
   }
   ```

   The **`if: "Bash(gh *)"`** (Claude Code **v2.1.85+**) scopes the hook to `gh` commands, so the script only spawns when you actually call GitHub — not on every Bash tool call. It strips leading `VAR=value` and inspects subcommands in compound commands; the script still self-checks that the segment is a PR creation.

   **Trade-off for this gate:** `if` matches by command *name*, so an absolute-path invocation (`/opt/homebrew/bin/gh pr create`) would skip the hook and open a PR without the trailer check. That's a rare path (agents type `gh`, not the full path), but for a security-relevant gate it's a real gap — if you want full coverage, **omit `if`** and let the hook fire on every Bash call (the script self-filters, just less cheaply). Omit it, too, on builds older than v2.1.85.

3. Restart Claude Code — hooks load at session start and never hot-swap. Confirm with `/hooks`.

## What it does

On every Bash tool call it splits the command into shell segments (quoting respected, so a commit message that mentions the phrase is not read as a PR) and checks whether any segment is a `gh` invocation that creates a PR — `gh … pr … create` with flags interleaved, or `gh api …/pulls`. If so, it resolves the PR's base branch locally (an explicit `--base`, else `origin/HEAD`, else `origin/main`/`origin/master` — **no network**) and greps `git log <base>..HEAD` for an `Adversarial-Review:` trailer. Found → the PR proceeds. Absent → exit 2 blocks the tool call and the stderr message tells the agent to run the review first.

Deliberately fail-open in every state except the one it exists to catch (reviewable commits, no disposition): not a Bash call, not a PR-creating segment, not a git repo, no resolvable base, no commits ahead, an unparseable command, or any git error — all allow. A gate that false-positives on weird repo shapes or legitimate commits gets uninstalled; one that only fires on the real miss gets kept.

## Known limitations (accepted)

These are the price of a fail-open speed bump; closing them isn't worth the complexity or the false-block risk:

- **Deliberate evasion isn't stopped** — a `gh` alias, `gh api` through a non-`/pulls` path, or a different tool can open a PR the matcher never sees. Out of scope by design; the target is forgetfulness, not adversarial bypass.
- **Inherited trailers pass** — a branch stacked on an already-reviewed branch inherits its trailer in `base..HEAD`, so its own new commits ride through. The skill's re-review rule still governs the human; the hook won't catch this case.
- **`cd`-into-another-repo compound commands** (`cd ../other && gh pr create`) are measured against the session's repo, not the one `gh` runs in.

## Test it without creating a PR

```bash
HOOK=~/.agents/skills/adversarial-review/resources/hooks/check-adversarial-review.py
# from a branch with no trailer — expect exit 2 and the BLOCKED message:
echo '{"tool_name":"Bash","tool_input":{"command":"gh pr create"},"cwd":"'"$PWD"'"}' | "$HOOK"; echo "exit=$?"
# any non-PR command — expect exit 0, silence:
echo '{"tool_name":"Bash","tool_input":{"command":"git status"},"cwd":"'"$PWD"'"}' | "$HOOK"; echo "exit=$?"
```
