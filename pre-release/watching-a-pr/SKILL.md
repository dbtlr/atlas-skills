---
name: watching-a-pr
description: "Watch an open GitHub PR and drive it to done — arm the background PR watcher, then on each wake route the batch it returns (address human review comments, fix red CI, announce green) and re-arm, until the PR merges (run the merged cleanup + reconcile stragglers) or the watch times out. Invoked directly with a PR number, or by the post-github-tool-call nudge when it is present. Primary agent / controller only."
---

# watching-a-pr

The engagement loop around an open PR. It runs the stateless **[pr_watcher.py](pr_watcher.py)** in the background; each time the watcher exits with a batch, this skill **routes** the batch and **re-arms** the watcher — so you review the PR in GitHub (where the diff is) and the agent picks up your inline comments, fixes red CI, and finishes the job, waking you only when it needs you.

> **Primary agent / controller only.** This drives session-level flow (posts to the PR, pushes fixes, may invoke `/merged`). A subagent never runs it.

## The model (read once)

The watcher is a background process. A background process can only re-invoke you when it **exits** — it doesn't stream. So the loop is: **arm → (it exits with a batch) → route the batch → re-arm with the advanced cursor → …** until a terminal.

- **You own the cursor.** The watcher is stateless; every normal result carries a `cursor`, and you pass it straight back as `--since` on the next arm. That is the entire continuity mechanism — don't reconstruct it, just round-trip it. (An operational-error result carries none — §4 says to reuse the last one.)
- **Every wake is a batch, not one event.** Several comments, a gate flip, and a merge can all arrive together. Process the *whole* batch before deciding to re-arm or stop.

## 1. Arm the watcher

Resolve the PR number and repo from context — the `post-github-tool-call` nudge (when present), the PR you just created, or the user's ask. Then launch the watcher **in the background** and end your turn — let it run detached; the harness re-invokes you when it exits.

**How you arm depends on whether the PR already has activity — get this right or you silently drop pre-existing feedback:**

- **A PR you just opened** (no comments/gates yet) — omit `--since`; the watcher baselines and reports only what arrives after:

  ```bash
  python3 <this-skill-dir>/pr_watcher.py --pr <N> --repo <owner/name>
  ```

- **A PR that may already carry comments or a settled gate** (a nudge on an existing PR, or resuming a watch) — arm with a **zero-cursor** so existing activity is surfaced and reconciled, not baselined away:

  ```bash
  python3 <this-skill-dir>/pr_watcher.py --pr <N> --repo <owner/name> \
    --since '{"issue_comment_hw":0,"review_comment_hw":0,"review_hw":0}'
  ```

- **A re-arm** — pass the `cursor` from the last result verbatim (see §5):

  ```bash
  python3 <this-skill-dir>/pr_watcher.py --pr <N> --repo <owner/name> --since '<cursor JSON>'
  ```

**Keep the cursor you last armed with** — you need it to recover from a watcher error (§4) without losing the outage window.

## 2. Route the batch

When the watcher exits, its stdout is `{ "events": [...], "cursor": {...}, "terminal": "merged"|"timeout"|null }` (a nonzero exit with `{"error": ...}` is an operational failure — see §4). Process **every** event, in order:

| Event `kind` | Do |
| --- | --- |
| `review_comment` (has `path`/`line`/`diff_hunk`) | Read the comment against that code location. Address it per the **autonomy boundary** below, then **reply on the PR** with the watermark (§3). |
| `issue_comment` / `review` | Same — treat as feedback; assess and address or reply. |
| `gates` `state: RED` (`failing: [...]`) | Inspect the named failing checks, fix the cause, push. A fix that is **mechanical** (lint, formatter, flaky retry) needs no re-review; a fix that **changes logic** warrants a fresh review (e.g. the harness's native review engine) before it counts as done. |
| `gates` `state: GREEN` | Tell the user the PR is **ready for their review**, with a 2–3 line summary of what's in it plus any fixes made since it opened. Keep watching. **Unless a `merge` event is also in this batch** (auto-merge settled green and merged in one poll) — then skip this announcement; the merge terminal (§4) supersedes it. |
| `merge` | Terminal — handle in §4. |

### The autonomy boundary

- **Address-and-push** a bounded, local change (rename, a line fix, a doc tweak, a clarified comment) — then reply noting what you changed.
- **Propose-and-wait** for anything broader (restructure, a design change, anything touching more than the commented site) — reply with your proposed approach and wait for the user, rather than pushing it unbidden.
- Either way, a comment you consciously decline gets a reply **stating why** — never silently skipped.

## 3. The watermark contract (load-bearing)

Every comment or reply **you** post to the PR must carry the watcher's watermark **on its own trailing line**, so the watcher filters your own words out and the loop can't feed on itself:

```
<your reply text>

<!-- claude-watcher:seen -->
```

Its own line matters: a human "Quote reply" that pulls the marker into a `> ` quote is *not* treated as yours, so their reply still reaches you.

Post with the right `gh` call for the kind you're answering — the inline-reply endpoint 404s for the others:

- `review_comment` (inline) — reply in-thread: `gh api repos/<owner>/<name>/pulls/<N>/comments/<id>/replies -f body='…'`
- `issue_comment` — a new PR comment: `gh pr comment <N> --body '…'`
- `review` — formal-review replies don't thread; acknowledge with a PR comment (`gh pr comment <N>`) referencing it.

Every one of these bodies **ends in the marker line**. And **never submit a body-less or watermark-less formal review** (an Approve/Request-changes with no body) — `pr_watcher` can't mark it as yours, so the watcher would surface your own review as new feedback and self-feed. If you post a formal review, put the marker in its body.

## 4. Terminals

- **`merged`** — the PR is in. First **process the rest of the batch** (a merge often lands alongside comments — don't discard them). Then invoke the **`merged`** skill for the cleanup ritual. Finally, **reconcile stragglers** — every comment in this final batch you did *not* fully address is offered to the user as a follow-up — *"the PR merged with N unaddressed comment(s); one reads like a real follow-up — file it?"* Stop watching.
- **`timeout`** — the watcher gave up after ~20 min of quiet. Report the PR's last-known state (gates, any open comments) and stop; the user can re-arm you or take it from here. Don't silently keep looping.
- **operational error** (nonzero exit, `{"error": ...}`) — the watcher itself failed (e.g. `gh` broke). The error payload carries **no cursor**, so re-arm with **the same cursor you last armed with** (§1) — *not* a fresh/omitted one, or the comments and gate changes from the outage window get baselined away and lost. Surface the error; re-arm once with that cursor if it looks transient, otherwise report and stop.

## 5. Re-arm

If the batch was **non-terminal**, launch the watcher again with the `cursor` from the result as `--since`, and end your turn. Re-arming with the advanced cursor is what keeps you from re-seeing what you just handled — and a fresh arm starts the poll fast again (5s), which is the backoff reset.
