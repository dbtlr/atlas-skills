---
name: consolidate-workspace
description: Consolidate the bound workspace's Session Logs — lift durable knowledge into the workspace (Brief, decisions, notes) and follow-ups into Mimir, mark each log consolidated via norn, and groom the Brief back to small. Scans only this workspace's unconsolidated logs. Primary agent only. (User observations → user.md/memory.md are consolidate-memory's job.)
---

# consolidate-workspace

Inspect this workspace's record of work, lift durable truth out of it into maintained context, then **prune what's now redundant**. Durable knowledge routes into the vault workspace; follow-ups route into Mimir.

> **Primary agent only.** Workspace-scoped — it consolidates only the **bound** workspace (the `workspace` from `.atlas.toml` / the Session Primer). The cross-workspace `user.md` / `memory.md` regeneration is **consolidate-memory**, a separate skill.

## What consolidation is (and isn't)

Consolidation is a **different job** from `write-session-log`. write-session-log keeps the *rolling narrative* (the Brief's Current State / Learnings) fresh; consolidation **lifts durable truth out of the frozen logs into standing homes, and prunes the rolling narrative back down.**

- **A fresh-looking Brief is NOT evidence that consolidation has run.** Litmus: *if a fact only lives in a dated Current-State paragraph or a per-session Learnings bullet, it is not consolidated yet — that's narrative, not maintained context.* Don't mistake a maintained Current State for a finished job.
- **The frozen Session Log IS the durable record of *what happened*.** Maintained context carries only the *lifted residue*: a sharpened term → glossary, a hard-to-reverse decision → ADR, a durable principle → a `notes/` file, an open thread → the Brief/board. **Don't duplicate the log into the Brief.** The same content living in the log *and* a Current-State paragraph *and* a Learnings bullet is the bloat signature — **triplication is the smell.**

## Preflight — norn is required

This skill drives **norn** to find and mark Session Logs; there is no fallback. Check it's available before doing anything:

```bash
command -v norn || { echo "consolidate-workspace requires the 'norn' CLI, which was not found on PATH. Install norn and ensure it's on your PATH, then re-run."; exit 1; }
```

If `norn` is missing, **stop and tell the user to install norn and put it on their PATH** — do not fall back to manually scanning `artifacts/session-logs/`.

## 1. Find this workspace's unconsolidated logs

There's no watermark file. Each Session Log carries a `workspace_consolidated` flag, so ask **norn** for the ones still open in this workspace:

```bash
norn find --eq type:session-log --eq workspace:<workspace> --eq workspace_consolidated:false
```

Each returned log's **Consolidation Candidates** section is a unit of work; process oldest-first. The companion flag `memory_consolidated` belongs to **consolidate-memory** — don't read or touch it here.

## 2. Route each candidate — but verify first

Per `resources/consolidation-candidates.md`. **Before routing any candidate, verify it:**

- **Dedup** — is it already captured (Brief, an ADR, the glossary, or the work tracker)? If so, don't re-add. **Don't duplicate.**
- **Still applies?** — carried tech-debt rots. Check the candidate against the live code/state before filing; a follow-up may already be fixed, moot, or subsumed by other planned work. File only what survives. (Verify, don't assume — this is the operator's standing expectation, not an optional courtesy.)
- **Recurring?** — a candidate carried across **≥2 runs** is itself the signal to act: file it or force a decision now; don't let it be "carried" again.

| Bucket | Routes to |
|--------|-----------|
| Durable knowledge | Workspace Brief (below the rule) / a `decisions/` ADR / a `notes/` note |
| Future opportunities | a **Mimir** task (`mimir` CLI) if the repo tracks work there — never re-grow a task list the workspace has migrated out |

- Promote durable knowledge into the right maintained file; **don't duplicate** what's already there.
- For a hard-to-reverse decision, write a real ADR. For a durable *principle* (a generative rule, not a decision), prefer a `notes/` file over bloating the Brief.
- For a follow-up / tech-debt / open-question, file it where the workspace tracks work, after the dedup + still-applies checks above.
- **User observations are not this skill's bucket.** The `collaboration-pattern` candidates feed `shared/user.md` / `shared/memory.md`, which span **all** workspaces — that's **consolidate-memory**'s job, keyed on the separate `memory_consolidated` flag. Leave them for it; don't rewrite the shared profile from one workspace's logs.
- A consolidated Session Log is **spent** — leave it frozen, but it's now prunable, not a permanent archive.

### Mark the log consolidated

Once a log's durable-knowledge + future-opportunity candidates are routed (or confirmed already-captured by the dedup check), mark it so it drops out of the scan:

```bash
norn set <log path> --field-json workspace_consolidated=true --yes
```

This touches only `workspace_consolidated` — never `memory_consolidated`.

## 3. Groom the Brief (a consolidation output, not a side task)

Consolidation isn't done until the Brief is **small again**. Follow `resources/workspace-hygiene.md`; operationally:

- **Prune the spent narrative.** Once a log is consolidated, its narrative is redundant with the frozen log — remove it from the Brief. The below-the-rule rolling sections (**Current State**, **Learnings / Recent Sessions**) must **not** accumulate one entry per session.
- **Current State = current position, not a changelog.** It should read as orientation — current position, open explorations, stable working norms — not a session-by-session history. Collapse or drop entries older than the last meaningful boundary (e.g. the last release/milestone).
- **Learnings.** Per-session learning bullets duplicate the logs — drop them. Distilled, durable *principles* worth keeping go to a `notes/` file with a one-line Brief pointer, not an ever-growing inline list.
- **Open Questions.** Drop resolved items (they're folded into ADRs/glossary as they close); keep only what's genuinely open.
- **Zones.** Groom the **below-the-rule** zone freely; touch the **above-the-rule** manifest (overview, tech stack, key paths, conventions, navigation) only for factual pointer updates, never to rewrite human-authored content.
- **Sanity check:** if the Brief reads like a log of what happened rather than the context a *new* session needs, it isn't groomed yet.

## 4. Record the run

There's no state file to advance — the per-log `workspace_consolidated` flags **are** the record. Briefly report what was promoted and where, and what was dropped as stale/duplicate.

## Notes

Two flags, two skills: `workspace_consolidated` (this skill) and `memory_consolidated` (**consolidate-memory**). Each scans and marks only its own flag via norn, so a log is independently consolidated for its workspace and for the shared profile — neither blocks the other.
