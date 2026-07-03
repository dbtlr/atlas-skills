---
name: watching-a-pr
description: "Watch an open GitHub PR and drive it to done — arm the background PR watcher, then on each wake route the batch it returns (address human review comments, fix red CI, announce green) and re-arm, until the PR merges (run the merged cleanup + reconcile stragglers) or the watch times out. Invoked by finishing-a-task after a PR is opened, or by the post-github-tool-call nudge. Primary agent / controller only."
---

# watching-a-pr

The engagement loop around an open PR. It runs the stateless **[pr_watcher.py](pr_watcher.py)** in the background; each time the watcher exits with a batch, this skill **routes** the batch and **re-arms** the watcher — so you review the PR in GitHub (where the diff is) and the agent picks up your inline comments, fixes red CI, and finishes the job, waking you only when it needs you.

> **Primary agent / controller only.** This drives session-level flow (posts to the PR, pushes fixes, may invoke `/merged`). A subagent never runs it.

## The model (read once)

The watcher is a background process. A background process can only re-invoke you when it **exits** — it doesn't stream. So the loop is: **arm → (it exits with a batch) → route the batch → re-arm with the advanced cursor → …** until a terminal.

- **You own the cursor.** The watcher is stateless; it returns a `cursor` in every result, and you pass it straight back as `--since` on the next arm. That is the entire continuity mechanism — don't reconstruct it, just round-trip it.
- **Every wake is a batch, not one event.** Several comments, a gate flip, and a merge can all arrive together. Process the *whole* batch before deciding to re-arm or stop.

## 1. Arm the watcher

Resolve the PR number (from context or the `post-github-tool-call` nudge) and the repo, then launch the watcher **in the background** and end your turn — let it run detached; the harness re-invokes you when it exits:

```bash
python3 <this-skill-dir>/pr_watcher.py --pr <N> --repo <owner/name>
```

On the **first** arm, omit `--since` (the watcher baselines to the PR's current state and only reports what arrives after). On a **re-arm**, pass the cursor from the last result verbatim:

```bash
python3 <this-skill-dir>/pr_watcher.py --pr <N> --repo <owner/name> --since '<cursor JSON>'
```

## 2. Route the batch

When the watcher exits, its stdout is `{ "events": [...], "cursor": {...}, "terminal": "merged"|"timeout"|null }` (a nonzero exit with `{"error": ...}` is an operational failure — see §4). Process **every** event, in order:

| Event `kind` | Do |
| --- | --- |
| `review_comment` (has `path`/`line`/`diff_hunk`) | Read the comment against that code location. Address it per the **autonomy boundary** below, then **reply on the PR** with the watermark (§3). |
| `issue_comment` / `review` | Same — treat as feedback; assess and address or reply. |
| `gates` `state: RED` (`failing: [...]`) | Inspect the named failing checks, fix the cause, push. A fix that is **mechanical** (lint, formatter, flaky retry) needs no re-review; a fix that **changes logic** re-enters the `adversarial-review` proportionality gate before it counts as done. |
| `gates` `state: GREEN` | Tell the user the PR is **ready for their review**, with a 2–3 line summary of what's in it plus any fixes made since it opened. Keep watching. |
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

Its own line matters: a human "Quote reply" that pulls the marker into a `> ` quote is *not* treated as yours, so their reply still reaches you. Post replies with `gh` (e.g. `gh api ... /pulls/<N>/comments/<id>/replies -f body=...`), body ending in the marker line.

## 4. Terminals

- **`merged`** — the PR is in. First **process the rest of the batch** (a merge often lands alongside comments — don't discard them). Then invoke the **`merged`** skill for the cleanup ritual. Finally, **reconcile stragglers** — every comment in this final batch you did *not* fully address is offered to the user as a follow-up — *"the PR merged with N unaddressed comment(s); one reads like a real follow-up — file it?"* Stop watching.
- **`timeout`** — the watcher gave up after ~20 min of quiet. Report the PR's last-known state (gates, any open comments) and stop; the user can re-arm you or take it from here. Don't silently keep looping.
- **operational error** (nonzero exit, `{"error": ...}`) — the watcher itself failed (e.g. `gh` broke). Surface the error; re-arm once if it looks transient, otherwise report and stop.

## 5. Re-arm

If the batch was **non-terminal**, launch the watcher again with the `cursor` from the result as `--since`, and end your turn. Re-arming with the advanced cursor is what keeps you from re-seeing what you just handled — and a fresh arm starts the poll fast again (5s), which is the backoff reset.
