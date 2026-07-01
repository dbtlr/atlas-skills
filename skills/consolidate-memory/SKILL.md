---
name: consolidate-memory
description: Consolidate user observations across ALL workspaces' Session Logs into the shared profile — regenerate user.md (how the human works) and memory.md (the agent's cross-project operating knowledge), merge-not-clobber, then mark each log via norn. Global and on-demand; the counterpart to consolidate-workspace. Primary agent only.
---

# consolidate-memory

The **global** counterpart to `consolidate-workspace`. Where that skill lifts a single workspace's durable knowledge into that workspace, this one lifts **user observations** out of **every** workspace's Session Logs into the **shared profile** — `shared/user.md` (the human) and `shared/memory.md` (the agent's cross-project operating knowledge).

> **Primary agent only. Global, not workspace-bound** — it reads logs across all workspaces and writes the vault-global Shared Workspace. It replaces the retired weekly `partner_model.md` consolidation loop.

## Preflight — norn is required

This skill drives **norn** to find and mark Session Logs; there is no fallback. Check it's available before doing anything:

```bash
command -v norn || { echo "consolidate-memory requires the 'norn' CLI, which was not found on PATH. Install norn and ensure it's on your PATH, then re-run."; exit 1; }
```

If `norn` is missing, **stop and tell the user to install norn and put it on their PATH** — do not fall back to manually scanning `artifacts/session-logs/`.

## 1. Find logs with unconsolidated observations

There's no watermark file. Each Session Log carries a `memory_consolidated` flag. Scan **all** workspaces (no `workspace:` filter — this is the global run):

```bash
norn find --eq type:session-log --eq memory_consolidated:false
```

The **User observations** section of each returned log's Consolidation Candidates (the `collaboration-pattern` items) is the unit of work. The companion flag `workspace_consolidated` belongs to **consolidate-workspace** — don't read or touch it here. Process a batch, then regenerate (§2) once, from the whole batch — never rewrite the profile per-log.

## 2. Regenerate `user.md` + `memory.md`

Gather the user-observation candidates across the batch, then update the two shared files. **Split by subject:**

- **`shared/user.md` (the human)** — how the collaborator thinks, communicates, decides, and works. Durable truths *about the person*.
- **`shared/memory.md` (the agent)** — reusable operating craft and environment/tooling facts the agent carries across projects. Durable truths *about doing the work*.

**Merge, don't clobber.** These files are hand-curated and load-bearing (they're Active Context). Update them in place — merge new signal into existing bullets, correct what's stale, delete what's superseded. **Never** regenerate from scratch or drop the hand-authored environment/tooling facts in `memory.md`.

**Editorial constraints** (carried from the retired partner-model consolidation packet):

- **Budget.** Target ~25–35 bullets per file; never exceed 40 without saying why in the run report.
- **Prefer deletion, merging, and correction over addition.** The profile is curated context, not an append log.
- **Keep only facts that change how a fresh agent behaves across projects tomorrow.** If it only matters to one project, it isn't profile material — it belongs in that workspace (via `consolidate-workspace`), not here.
- **Strip the project-specific.** No exact project names, command names, issue/PR numbers, or stale workspace lists. If a project-specific observation contains a reusable *principle*, keep only the principle.
- **One observation, one home.** A pattern about the human → `user.md`; the same insight framed as agent craft → `memory.md`. Don't double-file.

## 3. Mark each processed log

After a log's user-observation bucket has been folded in (or confirmed already-captured), mark it so it drops out of the scan:

```bash
norn set <log path> --field-json memory_consolidated=true --yes
```

This touches only `memory_consolidated` — never `workspace_consolidated`.

## 4. Record the run

There's no state file to advance — the per-log `memory_consolidated` flags **are** the record. Briefly report what changed in `user.md` / `memory.md` (added / merged / corrected / deleted), and how many logs were marked.

## Notes

Two flags, two skills: `memory_consolidated` (this skill) and `workspace_consolidated` (**consolidate-workspace**). Each scans and marks only its own flag via norn, so a log is independently consolidated for the shared profile and for its workspace — neither blocks the other.

**Trigger:** on-demand for now — run it when the profile is due a refresh. *(Open: it may later ride a schedule, e.g. a periodic loop, once it's stable and needs no operator input.)*
