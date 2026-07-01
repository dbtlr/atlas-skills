---
name: consolidate-memory
description: Consolidate user + agent-craft observations from ALL workspaces' Session Logs into the shared profile via a weighted extract→reduce→reconcile pipeline (ADR 0017) — profile-blind extractors mine whole logs into a durable observations ledger, then a computed spread×decay weight reconciles it into user.md and memory.md. Global and on-demand; the counterpart to consolidate-workspace. Primary agent only.
---

# consolidate-memory

The **global** counterpart to `consolidate-workspace`. Where that skill lifts a single
workspace's durable knowledge into that workspace, this one lifts **observations about
the human and the craft** out of **every** workspace's Session Logs into the **shared
profile** — `shared/user.md` (the human) and `shared/memory.md` (the agent's
cross-project operating knowledge).

It is a **weighted, sub-agent pipeline** (ADR 0017), not a one-shot rewrite. The v1
"read the observation bucket and edit the profile" had a fatal bias — the agent
over-weighted the current session and could only add. v2 replaces it with
**extract → reduce → reconcile** over a durable, accumulating ledger
(`shared/observations.md`), where a bullet earns its place by **computed weight**
(spread across workspaces × recency decay), not by having been seen just now.

> **Primary agent only. Global, not workspace-bound** — it reads logs across all
> workspaces and writes the vault-global Shared Workspace.

```
memory_consolidated:false logs ──shard by workspace──▶ [extract] profile-blind sub-agent per workspace
                                                              │ observations (+ provenance)
                                                              ▼
                                              [reduce] one sub-agent → observations.md ledger
                                                              │
                                          mark every extracted log memory_consolidated:true
                                                              │
                                    [reconcile] primary: weights.py → edit user.md / memory.md
```

The three moves are governed by two rubrics — read them when you reach each step:

- **Extract + reduce** → [`references/extraction-rubric.md`](references/extraction-rubric.md)
- **Reconcile** → [`references/reconcile-rubric.md`](references/reconcile-rubric.md)

## Preflight — hard dependencies

Three hard dependencies, no fallbacks. Confirm before doing anything:

1. **`norn` and `python3` on PATH:**

   ```bash
   command -v norn    || { echo "consolidate-memory requires the 'norn' CLI on PATH. Install it and re-run."; exit 1; }
   command -v python3 || { echo "consolidate-memory requires python3 (for weights.py). Install it and re-run."; exit 1; }
   ```

2. **Sub-agent dispatch.** Extraction is **always** a fresh sub-agent (even for a
   one-log batch) — that clean context *is* the bias fix. If your harness can't
   dispatch sub-agents, stop; do not run extraction inline in this (context-polluted)
   session.

If `norn` or `python3` is missing, **stop and tell the user to install it** — never
fall back to hand-scanning `artifacts/session-logs/` or eyeballing weights.

## 1. Find the batch

Each Session Log carries a `memory_consolidated` flag. Scan **all** workspaces (no
`workspace:` filter — this is the global run). Pull **every** match with both the
grouping key and the mark target — `find` defaults to a **limit of 10**, which would
silently truncate a global sweep, so pass `--no-limit`:

```bash
norn find --eq type:session-log --eq memory_consolidated:false \
  --no-limit --format json --col workspace,.path
```

Output is `{ "documents": [ { "frontmatter": {"workspace": …}, "path": … } ], "total": N }`.
**Group the documents by `frontmatter.workspace`** — that's the extractor unit (§2) —
and keep each doc's **`path`** for marking (§4). Check `returned == total` to confirm
nothing was truncated.

The companion flag `workspace_consolidated` belongs to **consolidate-workspace** —
don't read or touch it here. An empty batch is not a reason to skip reconcile (§5) —
decay may still have changed weights.

## 2. Extract (map) — one fresh, profile-blind sub-agent per workspace

For each workspace group, dispatch a **fresh** sub-agent per the **Map** section of the
extraction rubric. Two rules are load-bearing:

- **Profile-blind.** Do **not** paste `user.md` / `memory.md` / `observations.md` into
  the prompt, and instruct it not to read them. An extractor that has seen the profile
  echoes it back.
- **Whole-log.** It mines the entire log (not just the "User observations" bucket) and
  returns observations with provenance `{statement, bucket, log, workspace, date}`.

Hand each extractor the rubric and its workspace's log paths; collect the outputs. (A
workspace with a large backlog can be chunked across several extractors — see the
rubric; the unit stays the workspace.)

## 3. Reduce — one sub-agent writes the ledger

Dispatch a **single** sub-agent with **all** extractor outputs + the current
`observations.md`, per the **Reduce** section of the extraction rubric. It semantically
clusters, appends dated evidence to matching clusters or creates new ones, and writes
`observations.md`. It never computes weight and never prunes.

## 4. Mark every extracted log

After reduce has written, mark **every log dispatched to an extractor** — including
thin ones that yielded nothing (they were still extracted from; leaving them unmarked
re-scans them forever). Use each doc's `path` from §1's batch:

```bash
norn set <path> --field-json memory_consolidated=true --yes
```

This touches only `memory_consolidated` — never `workspace_consolidated`. The flag
means **"extracted into the ledger,"** not "in the profile."

## 5. Reconcile — weight-gated, into the profile

This step is run by **you (the primary)**, and is safe despite session pollution
because it is **weight-gated** — a single session can't manufacture spread×decay
weight. Run the helper that ships in this skill for the computed ranking (the path
resolves whether the skill is installed globally or run in-repo), then edit per the
reconcile rubric:

```bash
WEIGHTS="$(ls "$HOME/.claude/skills/consolidate-memory/weights.py" \
              "$HOME/.agents/skills/consolidate-memory/weights.py" \
              "skills/consolidate-memory/weights.py" 2>/dev/null | head -n1)"
python3 "$WEIGHTS" "$ATLAS_PATH/Workspaces/shared/observations.md" --format table
```

Then apply [`references/reconcile-rubric.md`](references/reconcile-rubric.md): add
strong clusters, strengthen represented ones, prune only stale-backed bullets
(conservative, reported), respect the managed/off-limits boundary and the budget.
**Run reconcile every time**, even on an empty batch (decay can prune on its own). On
early/thin-ledger runs it should *barely touch* the profile — never delete curated
bullets the ledger doesn't yet back (see the rubric's Cold start).

## 6. Report the run

There's no state file — the per-log flags and the ledger **are** the record. Report:
logs extracted + marked; ledger clusters added / evidence appended; and per profile
file, bullets added / strengthened / pruned (with justification) / flagged, plus any
budget drops.

## Notes

Two flags, two skills: `memory_consolidated` (this skill) and `workspace_consolidated`
(**consolidate-workspace**). Each scans and marks only its own flag via norn, so a log
is independently consolidated for the shared profile and for its workspace.

**Trigger:** on-demand — run it when the profile is due a refresh.
