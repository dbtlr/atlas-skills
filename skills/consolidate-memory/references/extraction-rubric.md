# Extraction rubric — map (extract) + reduce (cluster)

The heart of `consolidate-memory` v2 (ADR 0017). Consolidation is three moves:
**extract → reduce → reconcile**. This file governs the first two — the sub-agent
work that fills the observations ledger. Reconcile (turning the ledger into
`user.md` / `memory.md` by derived weight) is a separate rubric.

```
memory_consolidated:false logs
        │  sharded by workspace
        ▼
   [extract]  fresh, profile-blind sub-agent per workspace  →  observations (with provenance)
        │  all extractor outputs
        ▼
   [reduce]   one sub-agent: cluster + match + write        →  Workspaces/shared/observations.md
        │
        ▼
   primary marks every extracted log  memory_consolidated:true   (= "in the ledger", not "in the profile")
```

Both steps are **always** real sub-agent dispatches — even for a one-log batch.
Clean context is the whole point of the extract step; the primary running it inline
would reintroduce the v1 bias this design exists to kill.

---

## Map — the extractor sub-agent

**One fresh sub-agent per workspace shard.** It reads that workspace's
`memory_consolidated:false` Session Logs and returns observations. Nothing more.

### Two hard rules (this is the bias fix)

1. **Profile-blind.** The extractor must **never** read `shared/user.md`,
   `shared/memory.md`, or `shared/observations.md`. An agent that has seen the
   profile echoes it back; an agent that hasn't can only report what the logs
   actually show. Do not paste the profile into its prompt, and do not let it go
   look.
2. **Read the WHOLE log.** Mine every section — Overview, Context, What happened,
   Decisions, Deviations, *and* all three Consolidation-Candidate buckets — not
   just "User observations." The in-session author already curated that bucket
   under their own bias; the durable signal they under-weighted is usually in the
   narrative (a decision reversed, a correction taken, a check that caught an
   error). Reading only the curated bucket would inherit exactly the blind spot v2
   is built to remove.

### What counts as an observation

A durable, **cross-project** truth that would change how a fresh agent behaves
tomorrow. Two kinds — tag each with a `bucket` guess:

- **`user`** — about *the human*: how they think, decide, communicate, collaborate,
  what they value or reject. (→ eventually `user.md`.)
- **`memory`** — about *doing the work*: reusable operating craft, review/verification
  habits that pay off, environment & tooling facts. (→ eventually `memory.md`.)

The `bucket` is a **guess** — reconcile may re-home it. When one pattern fits both
(a human trait *and* the agent craft it implies), file it as the one that changes
behavior more; don't emit it twice.

### What to exclude (strip to the reusable principle)

- **Project-specific facts** — repo/product/command/flag names, PR/issue numbers,
  file paths, one workspace's architecture. If such a fact carries a reusable
  principle, keep only the principle and drop the specifics.
- **Event logging** — "shipped X", "fixed the test", "merged the PR." Work happened;
  that isn't an observation.
- **The obvious** — generic best practices true of any engineer anywhere.
- **One-offs** — a fluke with no recurrence signal. (Recurrence is proven later by
  cross-log spread, so don't over-filter here — but don't manufacture significance
  from a single throwaway line either.)

### Statement style

Crisp, one sentence, subject-first, present tense, self-contained, general enough
to apply to a project it has never seen. It becomes a cluster's **stable heading**,
so write it to last — and **no trailing period** (it is a heading, and the exact text
is the anchor reduce will match on).

- ✓ `Verifies reviewer and subagent claims against raw evidence before acting on them`
- ✓ `Reasons best against a concrete strawman — a sample artifact or named option — not an open prompt`
- ✗ `Drew wanted the observations.md PR reviewed before merge` (project-specific, an event)

### Output (one block per observation)

Emit a flat list in this shape — it mirrors the ledger, so reduce can place it with
minimal transformation. Provenance is **per observation** (a shard can span several
logs, each with its own date):

```markdown
### <the observation, as a durable one-sentence statement>
- bucket: user | memory
- log: <session-log filename stem, no extension>
- workspace: <workspace slug>
- date: <YYYY-MM-DD, the log's date>
```

`log`, `workspace`, and `date` come from the log being read. **`date` is the
`YYYY-MM-DD` prefix of the log's filename** — it is uniform across all logs
(frontmatter `created` is presence-only on historical logs and can differ across
midnight, so don't use it). Return only these blocks — no preamble, no profile
commentary. If a log yields nothing durable, say so and move on; a thin log is a
valid outcome, not a quota to fill (it still gets marked — see the orchestration
contract).

---

## Reduce — the clustering sub-agent

**One** sub-agent for the whole batch. Input: every extractor's output (blocks of
`### <statement>` + `bucket` / `log` / `workspace` / `date` fields) **plus** the
current `Workspaces/shared/observations.md`. Output: the updated ledger. It does
**not** touch `user.md` / `memory.md`, and it does **not** compute or store weight —
weight is derived later at reconcile.

### The job

Semantically cluster. For each incoming observation:

1. **Matches an existing cluster?** (same underlying pattern, even if worded
   differently) → **append one dated evidence line** under that cluster. Do **not**
   reword the heading — norn anchors edits on exact heading text, so a reworded
   heading orphans its evidence.
2. **Matches another *new* observation** (two extractors surfaced the same pattern)
   → merge them into one new cluster with both evidence lines.
3. **Otherwise** → create a new cluster.

Match on meaning, not string overlap. Two differently-worded lines about the same
trait are one cluster; superficially similar lines about different things are not.
When genuinely unsure, prefer a **new** cluster — a wrongly-split pair costs a little
weight; a wrongly-merged pair corrupts the signal and is hard to undo.

**Heading collision = a match, never a second cluster.** A cluster's heading *is* its
identity, and norn **refuses a duplicate heading** (the whole edit batch fails). So
before creating a new cluster, confirm its exact heading text isn't already present;
if it is, that is by definition the same cluster — append evidence to it instead.
This is why the "prefer new when unsure" rule above is about *meaning*, not about
minting a near-identical heading.

### Writing the ledger

Follow the format documented in `observations.md` itself ("Entry format" + "How to
write") — that file is the source of truth for structure; this rubric governs
*judgment*. **Pin the vault: every `norn edit`/`set` here must pass `-C "$ATLAS_PATH"`**
(norn keys off cwd/`.norn`, not `ATLAS_PATH`; a sub-agent running from another cwd will
otherwise write to the wrong vault or a stray `.norn`). In short:

- **New cluster** → `append_to_section` on heading `Clusters`; content is a full
  `### <statement>` block with the fields **exactly as `observations.md` shows them** —
  `- **bucket:** …`, `- **status:** active`, `- **evidence:**`, then the indented
  evidence line(s). (Keep the bold markers; a bare `bucket:` degrades but drifts.)
- **New evidence** → `append_to_section` on the existing cluster's exact heading, a
  single `  - YYYY-MM-DD | <workspace> | [[<log>]]` line (two-space indent nests it).
- **bucket** = the incoming guess; if a cluster's evidence disagrees, keep the
  dominant guess and leave re-homing to reconcile.
- **status** = `active` for every new cluster. Reduce never sets `archived` and never
  deletes — pruning is reconcile's job, downstream and weight-gated.

### Idempotency (and its limits)

**One evidence line per (log, date) per cluster.** Before appending, check the target
cluster doesn't already carry that log's line; before adding an incoming observation,
skip it if its `(log, date)` already appears under a cluster that matches it. This
makes a reduce **re-run over the same extractor output** a no-op.

It does **not** give full crash-recovery idempotency: if the run dies *after* reduce
writes but *before* the logs are marked (orchestration steps 3→4), those logs get
re-extracted next run, and LLM nondeterminism may reword a statement so it clusters
differently — which the per-cluster check won't catch. The bound on this is the
marking step: mark promptly after the write so the window is small, and accept that
semantic clustering can't be perfectly idempotent across re-extraction.

---

## Orchestration contract (what the primary does around the sub-agents)

The skill (`SKILL.md`) wires this; the contract the sub-agents rely on:

1. `norn -C "$ATLAS_PATH" find --eq type:session-log --eq memory_consolidated:false` →
   the batch. Group by `workspace`. (Pin the vault with `-C` on **every** norn call —
   norn resolves its vault from cwd/`.norn`, not from `ATLAS_PATH`; a bare call from
   the wrong cwd hits the wrong vault.)
2. Dispatch **one extractor per workspace group** (fresh context, profile-blind).
   A workspace with a large backlog may be sub-sharded, but the unit is the workspace.
3. Collect all extractor outputs; dispatch **one** reduce agent with them + the
   current `observations.md`.
4. After reduce has written, mark **every log dispatched to an extractor** — not just
   the ones that produced clusters:
   `norn -C "$ATLAS_PATH" set <log> --field-json memory_consolidated=true --yes`.
   The flag means **"extracted into the ledger,"** not "in the profile." A thin log
   that yielded nothing *was still extracted from*, so it must be marked too — else it
   is re-scanned on every future run forever (wasted work, and a re-extraction path
   that can duplicate evidence). The profile
   is updated separately by reconcile, on its own cadence, from the whole ledger.
