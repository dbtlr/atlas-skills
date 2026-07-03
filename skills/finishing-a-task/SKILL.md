---
name: finishing-a-task
description: "The workflow for finishing a task — MANDATORY at the moment you're about to declare work done, create a PR (`gh pr create`), or push/merge changes to the main branch. Confirms the task is actually complete, then requires a completed `adversarial-review` before the change leaves your hands, and after a PR is opened hands off to `watching-a-pr` to carry it through CI, review comments, and merge. The embodiment of 'not complete until verified by an adversarial agent and presented to a human.' Primary agent / controller only."
---

# finishing-a-task

The through-line from *"I think I'm done"* to *"merged and moved on."* Work is **not complete until it is verified — by an adversarial agent — and presented to a human.** This skill turns that rule into a sequence, orchestrating the skills that own each step rather than doing their jobs itself.

> **Primary agent / controller only.** This drives session-level flow (invokes `adversarial-review`, creates PRs, hands off to `watching-a-pr`). A subagent that built something reports back; the controller finishes the task.

<EXTREMELY-IMPORTANT>
If you are about to tell the user a task is **done**, about to run **`gh pr create`**, or about to **push or merge to the main branch**, and you have not run this workflow, STOP and run it now. These thoughts mean you are rationalizing:

| Thought | Reality |
| --- | --- |
| "It's obviously finished, I'll just open the PR" | Opening the PR *is* declaring it done. The workflow runs first, not after. |
| "The change is small — I'll just push to main" | Never push or merge to the main branch — all work ships as a PR. Small changes get a PR and a review too. |
| "I'll review it after I put the PR up" | After the PR is up, the human is already looking. Verify before you present, not after. |
| "I already read it over as I wrote it" | You re-derive your own blind spots. Verification is adversarial and fresh-context — that's `adversarial-review`, not self-review. |
| "This is just a doc/config tweak" | Then `adversarial-review`'s own proportionality gate will say so in one line. Let *it* decide the tier or the skip. |
</EXTREMELY-IMPORTANT>

## The workflow

Walk it in order. Each gate stops the task from "finishing" on a wrong assumption.

### 1. Are you actually finished?

If the task isn't complete — tests not written, a TODO still open, the feature only half-built — **STOP here.** Finishing-a-task is the *last* step, not a way to skip the work. Come back when the change is genuinely done and its own gates (build, lint, tests, a smoke if it has a runtime surface) are green.

### 2. Are you opening a PR?

All work ships as a PR — **never a direct push or merge to the main branch.** So:

- **Creating a PR for the user to review** → go to step 3.
- **Not yet — still local, not sharing** → there's nothing to finish; come back when you are.

### 3. Verify — run `adversarial-review` to completion

Invoke the **`adversarial-review`** skill and let it finish. It runs its proportionality gate (or declares a skip), the suppression scan, delegates the review, and drives the resolution loop until **every finding is in a terminal state** (fixed / dismissed-with-reason / deferred-to-a-tracked-task), then writes the `Adversarial-Review:` disposition trailer and presents the table.

**Do not continue past this step until that trailer exists on the branch.** The trailer is the proof the work was verified; it's what the pre-PR hook (when present) checks, and it's what makes "done" honest. If review surfaced fixes, they're part of the change now — re-run the earlier gates it may have invalidated.

### 4. Present and open the PR

Create the PR (`gh pr create`), carrying **adversarial-review's disposition table into the body** — the review's outcome is part of what you present to the human. This is where adversarial-review's "table in the PR body" actually happens: it produced and presented the table in chat at step 3; you place it in the body here. This is the "presented to a human" half of the rule.

(For a **declared skip**, adversarial-review produced only a skip trailer and no table — put the skip reason in the PR body instead.)

### 5. Hand off to `watching-a-pr`

Once the PR is open, invoke **`watching-a-pr`** with the PR number. It arms the background watcher and carries the PR the rest of the way — surfacing CI results, routing your inline review comments, and on merge running the `merged` cleanup and reconciling any stragglers. Your part of finishing-a-task ends here; the watch loop owns the PR until it merges or times out.

## What this skill composes

- **`adversarial-review`** — the verification step (3), **not a parallel gate**. Both fire at "about to `gh pr create`"; when you're finishing a task, start *here* and let this workflow invoke it. Reaching for `adversarial-review` directly still verifies the change, but skips the finish sequence — the PR presentation (4) and the watch hand-off (5). It owns the review engine, resolution loop, and trailer.
- **`watching-a-pr`** — the post-open loop (5). Owns the watcher, CI/comment routing, and the merge hand-off to `merged`.
- **`merged`** — invoked by `watching-a-pr` on merge; not called directly here.

finishing-a-task holds the *sequence* and its gates; each skill above owns its own step. The pre-PR enforcement hook (`adversarial-review`'s trailer gate) is the deterministic backstop for step 3 on harnesses with hooks — this skill is the language-first path that should make the hook rarely need to fire.

## Harness note

The full loop (hook backstop + background watcher) is a Claude Code capability. On a harness without background execution or hooks — notably Codex, which drives GitHub through its own tool — finishing-a-task runs as far as it can by language: verify via `adversarial-review`, present the PR, and rely on the human for the watch. The verify-before-present rule is portable; the watch is not.
