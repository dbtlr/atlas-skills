---
name: consolidate-sessions
description: Lift Consolidation Candidates out of frozen Session Logs into maintained context — durable knowledge to the workspace, follow-ups to the work tracker, user observations to the shared profile — and groom the Brief back to small. Run periodically or when Session Logs have accumulated. Primary agent only.
---

# consolidate-sessions

Inspect the record of work, lift durable truth out of it into maintained context, then **prune what's now redundant**. Durable knowledge routes into the vault workspace, follow-ups into Mimir, and user observations into the shared profile.

> **Primary agent only.**

## What consolidation is (and isn't)

Consolidation is a **different job** from `write-session-log`. write-session-log keeps the *rolling narrative* (the Brief's Current State / Learnings) fresh; consolidation **lifts durable truth out of the frozen logs into standing homes, and prunes the rolling narrative back down.**

- **A fresh-looking Brief is NOT evidence that consolidation has run.** Litmus: *if a fact only lives in a dated Current-State paragraph or a per-session Learnings bullet, it is not consolidated yet — that's narrative, not maintained context.* Don't mistake a maintained Current State for a finished job.
- **The frozen Session Log IS the durable record of *what happened*.** Maintained context carries only the *lifted residue*: a sharpened term → glossary, a hard-to-reverse decision → ADR, a durable principle → a `notes/` file, an open thread → the Brief/board. **Don't duplicate the log into the Brief.** The same content living in the log *and* a Current-State paragraph *and* a Learnings bullet is the bloat signature — **triplication is the smell.**

## 1. Find what's new

Track the last run in a small state file:
```
<ATLAS_PATH>/artifacts/.atlas-consolidate-state.toml   # last_run = "<ISO ts>"
```
Read it; process Session Logs in `<artifacts_dir>/session-logs/` newer than `last_run` (all of them on first run). Process in batches if a stale watermark has let many accumulate; the per-log **Consolidation Candidates** section is the unit of work.

> **Watermark scope.** This cursor governs *this skill's* routing (durable knowledge + follow-ups). It does **not** cover the cross-project shared-profile regeneration (§2, user observations) — that runs across all workspaces and needs its own cursor. Advancing `last_run` past logs whose observation-bucket you deferred means a future profile run keyed on this cursor would skip them; if you defer that bucket, say so in the run report (§4) so the cursor isn't mistaken for "fully consolidated."

## 2. Route each candidate — but verify first

Per `resources/consolidation-candidates.md`. **Before routing any candidate, verify it:**

- **Dedup** — is it already captured (Brief, an ADR, the glossary, or the work tracker)? If so, don't re-add. **Don't duplicate.**
- **Still applies?** — carried tech-debt rots. Check the candidate against the live code/state before filing; a follow-up may already be fixed, moot, or subsumed by other planned work. File only what survives. (Verify, don't assume — this is the operator's standing expectation, not an optional courtesy.)
- **Recurring?** — a candidate carried across **≥2 runs** is itself the signal to act: file it or force a decision now; don't let it be "carried" again.

| Bucket | Routes to |
|--------|-----------|
| Durable knowledge | Workspace Brief (below the rule) / a `decisions/` ADR / a `notes/` note |
| Future opportunities | a **Mimir** task (`mimir` CLI) if the repo tracks work there — never re-grow a task list the workspace has migrated out |
| User observations | the shared profile (`shared/user.md` / `shared/memory.md`) regeneration, cross-project |

- Promote durable knowledge into the right maintained file; **don't duplicate** what's already there.
- For a hard-to-reverse decision, write a real ADR. For a durable *principle* (a generative rule, not a decision), prefer a `notes/` file over bloating the Brief.
- For a follow-up / tech-debt / open-question, file it where the workspace tracks work (`status: backlog`), after the dedup + still-applies checks above.
- **User observations are cross-project and the route changed.** The legacy `partner_model_log.jsonl` shim is **retired** — do not append to it. Observations feed the regeneration of the shared profile (`shared/user.md` / `shared/memory.md`), which spans **all** workspaces. A single-workspace consolidate run should **stage** new observations for that regeneration, **not** rewrite the shared profile from one workspace's logs (that skews it). Defer the rewrite to the cross-project run and note the deferral (§4).
- A consolidated Session Log is **spent** — leave it frozen, but it's now prunable, not a permanent archive.

## 3. Groom the Brief (a consolidation output, not a side task)

Consolidation isn't done until the Brief is **small again**. Follow `resources/workspace-hygiene.md`; operationally:

- **Prune the spent narrative.** Once a log is consolidated, its narrative is redundant with the frozen log — remove it from the Brief. The below-the-rule rolling sections (**Current State**, **Learnings / Recent Sessions**) must **not** accumulate one entry per session.
- **Current State = current position, not a changelog.** It should read as orientation — current position, open explorations, stable working norms — not a session-by-session history. Collapse or drop entries older than the last meaningful boundary (e.g. the last release/milestone).
- **Learnings.** Per-session learning bullets duplicate the logs — drop them. Distilled, durable *principles* worth keeping go to a `notes/` file with a one-line Brief pointer, not an ever-growing inline list.
- **Open Questions.** Drop resolved items (they're folded into ADRs/glossary as they close); keep only what's genuinely open.
- **Zones.** Groom the **below-the-rule** zone freely; touch the **above-the-rule** manifest (overview, tech stack, key paths, conventions, navigation) only for factual pointer updates, never to rewrite human-authored content.
- **Sanity check:** if the Brief reads like a log of what happened rather than the context a *new* session needs, it isn't groomed yet.

## 4. Record the run

Update the state file's `last_run` to now (accurate timestamp). Briefly report **what was promoted and where, what was dropped as stale/duplicate, and which buckets were deferred** (esp. the cross-project user-observations rewrite) so the watermark isn't mistaken for full consolidation.

## Notes

Keep the three routes in one place so their targets stay easy to maintain: durable knowledge → the vault workspace, follow-up work → a **Mimir** task, and `user.md`/`memory.md` → the cross-project shared-profile regeneration.
