---
name: merged
description: Post-merge cleanup ritual — run when the user says the working PR was merged ("/merged", "I merged it", "PR's in") to verify the merge on GitHub, return to an up-to-date main, and delete the finished branch or worktree. Composable args — "log" writes the Session Log, "next" picks up the next task; "log" always runs before "next". Primary agent only.
---

# merged

The post-merge ritual. The user merged the working PR in GitHub; get the local repo from "finished branch" back to "clean, up-to-date main" — safely — then optionally memorialize the session and pick up the next task.

> **Primary agent only.** This drives session-level flow (and may route to `write-session-log`); subagents never run it.

## Arguments

`/merged [log] [next]` — the args compose, in any order. Natural-language equivalents count as args too ("…and write the log", "what's next") for harnesses that pass none.

- *(none)* — cleanup only.
- `log` — after cleanup, invoke the **write-session-log** skill (before the report).
- `next` — after the report, start the next task.
- Both — whatever order given, `log` always runs before `next`, with the report between them. The log memorializes the finished work; starting new work first would bleed it into the record.

## The ritual

Work through in order. Each gate exists to stop something irreversible from happening on a wrong assumption.

Throughout, "main" means the repo's actual integration branch — resolve it first with `git symbolic-ref --short refs/remotes/origin/HEAD` (fallback `gh repo view --json defaultBranchRef`); don't assume it's literally named `main`.

### 1. Identify the branch

The branch being retired is the current branch (or the current worktree's branch). If already on main, or HEAD is detached, infer the just-merged branch from session context; if that's ambiguous, ask. Never guess at a branch to delete.

### 2. Verify the merge actually landed

```bash
gh pr view <branch> --json state,mergedAt,headRefOid,url
```

Two checks, both required:

- **The PR is `MERGED`.** `OPEN` → stop; not merged yet. `CLOSED` without merge → stop; closed-unmerged is a signal to surface, not a cleanup trigger. No PR found → stop and ask.
- **The local tip is what merged.** `git rev-parse <branch>` must equal `headRefOid`. If the local tip is *ahead* of `headRefOid`, there are commits that never made it into the PR — stop and show them. If it's unrelated, the branch name was probably reused and `gh` resolved an old PR — stop and surface. A `MERGED` state alone proves *a* PR for that name merged, not that *these* commits did.

Use `gh`, never `git branch --merged` — squash and rebase merges rewrite the commits, so the local merged-check can't see them land. This two-part verification is the one thing that makes the force-delete below safe.

### 3. Gate on uncommitted work

Dirty means non-empty `git status --porcelain` — **untracked files included**; a brand-new file that never made the PR is exactly the thing this gate protects. If dirty, stop and show the changes. Uncommitted work on a merged branch usually means something didn't make it into the PR — deleting the branch or worktree would silently destroy it. Let the user decide: discard, or carry along to main (carry = `git stash push -u`, which then rides the step 5 pop-and-review path).

### 4. Close the task in Mimir

In a Mimir-tracked repo (`.mimir.toml`), mark the task this PR carried as done — `mimir done <id>`; the user merging the PR *is* the approval. Do it now, while the branch still identifies the work — after cleanup nothing points back at it. If the task isn't obvious from session context or the branch/PR, ask rather than close the wrong one. No Mimir, or no task in flight → skip.

### 5. Return to main and delete the branch

- **Plain branch** — `git switch main`, then `git branch -d <branch>`; fall back to `-D` when `-d` refuses (expected after squash/rebase — step 2 already proved these exact commits landed).
- **Worktree** — move back to the main checkout, `git worktree remove <path>`, then delete the branch as above. If the remove refuses, that's a red flag, not a prompt to `--force`: something is still in the tree that steps 1–3 didn't account for — show the user what's there.
- `git fetch --prune` — GitHub usually auto-deletes the remote branch on merge; prune the stale tracking ref. If the remote branch survived, remove it with `git push origin --delete <branch>`.

### 6. Sync main

- If main's working tree is dirty, stash first — `git stash push -u -m "merged/pre-pull"` (`-u`: an untracked file the pull wants to write would otherwise abort it).
- `git pull --ff-only origin main`. If ff-only refuses, local main has diverged — stop, show `git log origin/main..main`, and resolve with the user. Never reset to force it.
- If anything was stashed, `git stash pop`, then summarize what the changes actually are (files and what they do) and ask — keep them sitting in the tree, or commit them to a fresh branch for review as their own PR? A pop conflict is the ugly path: stop, explain the conflict, and resolve it with the user rather than improvising.

### 7. Memorialize — `log`

If `log` was given, invoke **write-session-log** now, while the report is still ahead — the log closes out the finished work before anything new enters the session.

### 8. Report

Summarize the ritual: PR verified merged (link), Mimir task closed, branch/worktree deleted, main synced (what came in), anything stashed and popped, and whether the Session Log was written.

### 9. Pick up the next task — `next`

If `next` was given, find the next task after the report is out. In a Mimir-tracked repo (`.mimir.toml`), consult `mimir next`; one clear top task → start it. When the choice isn't obvious — several candidates, or no queue — present the options with enough detail to pick: what each task is, roughly its size, and which is recommended and why.
