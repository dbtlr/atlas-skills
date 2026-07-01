# Reconcile rubric — weight-gated ledger → profile

The third move of `consolidate-memory` v2 (ADR 0017): **extract → reduce →
reconcile**. Extract/reduce fill the observations ledger (see
[extraction-rubric.md](extraction-rubric.md)); **reconcile** turns that ledger into
the curated profile — `shared/user.md` (the human) and `shared/memory.md` (the
agent's operating craft) — by **derived weight**.

Unlike extract, reconcile is run by the **primary** (no fresh sub-agent needed), and
that is safe *precisely because it is weight-gated*: the primary may be
context-polluted from the session, but it cannot **manufacture weight** — weight comes
from dated evidence spread across workspaces, accumulated over time in the ledger. A
single session can add one hit to one cluster; it cannot make that cluster outweigh a
pattern seen ten times across five workspaces. The gate, not the reader's neutrality,
is what resists bias.

Reconcile **reads**, it does not advance a cursor: it consumes the *whole* ledger
every run and has **no flag of its own** (`memory_consolidated` belongs to reduce).
So it can run anytime — including a run with zero new logs, which still does real work
(decay may have pushed a bullet to stale; see "Decay can prune on its own").

## Inputs / outputs

- **In:** the whole `Workspaces/shared/observations.md` (all `status: active`
  clusters) + the current `user.md` and `memory.md`.
- **Out:** edited `user.md` / `memory.md`, in place. Nothing else. Reconcile never
  edits the ledger (no weight is written back — see below) and never touches
  `status`/evidence.

---

## The weight model

For each **active** cluster (skip `status: archived`):

```
weight = spread × Σ decay(now − hit_date)
  spread          = count of DISTINCT workspaces across the cluster's evidence
  decay(Δdays)    = 0.5 ^ (Δdays / 90)          # exponential, ~90-day half-life
  now             = today's date
```

**There is exactly one ordering: `weight`, computed by the formula above.** Rank and
budget by that single number — do not introduce a separate lexical sort. (Exact-weight
ties are broken deterministically — higher spread, then more-recent newest hit — purely
for reproducibility; that tiebreak never overrides weight.) "Spread-first"
is not a second rule; it is *why the formula behaves as it does*: spread is the
**multiplier**, so a cluster seen across many workspaces dominates one piled up in a
single workspace (that's local flavor — it belongs in *that* workspace's notes, not the
shared profile). Hit **count** and **recency** both live inside `Σ decay` — more hits
add terms, older hits shrink them — so the formula already embodies "spread-first,
recent-and-repeated next." Nothing ranks outside it.

**Don't compute this by hand — run the helper.** `weights.py` (this skill's directory)
parses the ledger and prints each active cluster's `{spread, count, newest_date,
weight, tier}`, ranked. Use its numbers as the authoritative ranking and tiering; your
judgment goes into the *actions* (add/strengthen/prune/flag/re-home), not the
arithmetic. Running it is what makes the gate *computed* rather than eyeballed. Only if
it cannot run, fall back to reading the drivers off the evidence lines — spread (it
multiplies, so it dominates), then the **mass of recent evidence** — and beware the
trap that *many* all-old hits still decay toward zero.

### Tiers (recency-gated, not magic numbers)

Tier on the decay scale (half-life ≈ 90d). **Staleness is gated on recency of the
newest hit** — this gate wins over spread, so a broad-but-quiet cluster is stale, not
strong (it stopped recurring; only its history remains):

- **stale** — **newest** hit older than ~2 half-lives (~180d). The pattern has gone
  quiet; weight has bled out **regardless of spread or count**.
- **strong** — newest hit **recent** (within ~1 half-life, ~90d) **and** spread **≥ 2**
  (seen in ≥2 workspaces). Current *and* cross-project.
- **aging** — everything between (recent but single-workspace, or newest hit 1–2
  half-lives old). Real but fading.

`spread ≥ 2` is a floor, not a nicety: a single-workspace cluster is never "strong" and
never enters the shared profile on its own (see Actions → Add).

---

## Managed vs. off-limits — the boundary reconcile must not cross

Reconcile governs **only**:

- **`user.md`** — the whole file (every section is consolidated truth about the human).
- **`memory.md` → the `## Operating lessons (carry across projects)` section only.**

**Off-limits — never edit, never prune, never reorder:** `memory.md`'s
`## Environment & tooling` section and any other hand-authored block. These are
human-curated facts with **no backing cluster by design** — so **"no backing cluster"
must never be read as "stale"** there. If you're unsure whether a section is managed,
treat it as off-limits and leave it.

Anchor every `norn edit` on the heading's **exact** text — `Operating lessons (carry
across projects)`, parenthetical included — not a shortened form, or the edit won't
match.

---

## Actions (tiered, conservative)

Match ledger clusters to profile bullets by meaning, then:

- **Add** — a **strong** cluster (recent **and** spread ≥ 2) **not** represented in the
  profile → add a bullet, in the right file/section (see routing). Only **strong** earns
  a new bullet: never add from an `aging` or spread-1 cluster — a single-workspace
  pattern is local, and stays in the ledger accruing evidence until it gains spread.
- **Strengthen** — a non-stale cluster **already** represented → refine the existing
  bullet in place (sharpen wording, merge in the new nuance). **Never duplicate** an
  existing bullet; one observation, one home.
- **Prune** — remove a managed bullet only when its backing **active** cluster has
  decayed to **stale** (newest hit gone quiet ~180d). This is the **sole** automated
  prune trigger (matching ADR 0017), and it is always **conservative and reported**.
- **Flag, never delete** — a managed bullet with **no matching active cluster** is
  ambiguous: it may predate the ledger, be a hand-authored survivor, or have had its
  cluster **archived** (manually retired — reconcile loads only `active` clusters, so an
  archived-backed bullet simply presents as unbacked; archiving thus *surfaces* a bullet
  for human attention, it does not auto-prune it). The ledger has *no opinion* on such a
  bullet, and silence is not a delete signal. Flag it and move on. Anything uncertain →
  flag, don't prune. A wrongly kept bullet is cheap; a wrongly deleted one loses curated
  knowledge.

**The grandfather rule (why "no cluster" ≠ "prune").** The profile predates the ledger,
which fills over many runs. An incumbent bullet the ledger doesn't yet speak to is
**grandfathered** — never pruned, never budget-evicted for lack of a cluster. Pruning
and budget act **only** on ledger-backed bullets; unbacked incumbents are, at most,
flagged. This is what makes the *first* runs safe (see Cold start).

**Re-homing.** A cluster's `bucket` was the extractor's *guess*. Reconcile decides the
real home: a truth about **the human** → `user.md`; reusable **agent craft / how to do
the work** → `memory.md` `Operating lessons`, regardless of the stored `bucket`. If a
bullet is clearly in the wrong file, move it (add to the right, remove from the wrong).

## Budget

**15–25 bullets per file.** (Tighter than the old single-file 25–35 — there are two
files now.) The profile is curated Active Context, not an append log. If a file is over
budget after add/strengthen, **drop the lowest-`weight` bullets** among the
**ledger-backed** ones, and **report the drops** — a strong new add evicting a weak
backed incumbent is the mechanism working.

**Budget never evicts an unbacked/flagged bullet.** Those have no computable weight —
"unmeasured" is not "weakest." So budget can only tighten a file once enough of its
bullets are ledger-backed to rank. If a file is over budget *only* because of
grandfathered incumbents (the normal early state), it stays over budget: **report it,
don't force it into range by deleting curated content.** The ledger earns the right to
prune as it accumulates.

## Cold start / thin ledger

The ledger is **seeded empty** and fills across many runs; on the first runs almost
every incumbent bullet is unbacked. This is the expected state, not a defect — and the
grandfather + budget rules above make it safe: **early runs are add/strengthen only.**
Concretely, when the ledger has little coverage:

- **Add/strengthen** the few clusters that *do* clear the bar (strong, spread ≥ 2).
- **Prune nothing** for absence of a cluster; **flag** unbacked incumbents at most.
- **Tolerate over-budget** — do not cut the profile down to 15–25 by deleting
  grandfathered bullets. Report the over-budget count and move on.

A run over an empty or near-empty ledger should therefore *barely touch* the profile.
If a proposed run would delete many curated bullets because "the ledger doesn't back
them," that is the failure this section exists to stop — halt and report instead.

## Decay can prune on its own

A reconcile run with **zero new logs** is **not** a no-op. `now` has advanced, so a
cluster that was `aging` last month may now be `stale`, and its bullet becomes a prune
candidate. This is recency doing its job — surface it in the report as such, not as
"nothing changed."

This is a **mature-ledger** behavior — it needs backed bullets old enough to cross into
stale. It does **not** contradict "early runs are add/strengthen only" (Cold start): a
thin ledger has no such aged-out backed bullets, so there is nothing for decay to prune
yet. "Thin ledger" and "mature ledger, no new logs this run" are different states.

---

## How to edit, and merge-not-clobber

`user.md` / `memory.md` are hand-curated, load-bearing Active Context. **Edit in place;
never regenerate from scratch, never reorder sections, never drop hand-authored
content.** Preserve each file's existing section structure and prose voice; you are
merging signal into a living document, not rebuilding it.

Use `norn edit` for surgical changes (`str_replace` to refine a bullet,
`append_to_section` to add one under the right heading, `replace_section` only when
rewriting a whole managed section deliberately). **Pin the vault on every call:
`norn -C "$ATLAS_PATH" edit …`** — norn resolves its vault from cwd/`.norn`, not from
`ATLAS_PATH`, so an unpinned call can edit the wrong vault. When you change a file,
bump its `modified` frontmatter: `norn -C "$ATLAS_PATH" set <file> --field-json modified=<now> --yes`.

## Report the run

No state file changes, so the report **is** the record. State, per file: bullets
**added**, **strengthened**, **pruned** (with the stale cluster that justified each),
**flagged** (ambiguous, left alone), and any **budget drops**. Pruning and re-homing
must always appear — a silent deletion of curated context is exactly the failure this
conservative posture exists to prevent.

## The weight helper

`weights.py` (this skill's directory) is the **canonical** weight source — the model
above is deterministic, and an LLM eyeballing decay across many dated lines is not:

    python3 weights.py "$ATLAS_PATH/Workspaces/shared/observations.md" --format table

It reads only `status: active` clusters from the `## Clusters` section (the format spec
and its fenced example are ignored), applies the exact model above (half-life 90d,
tiers as defined), and prints per-cluster `{heading, bucket, spread, count,
newest_date, weight, tier}` ranked by weight (`--format json` for machine use).
`--now YYYY-MM-DD` overrides the reference date (tests; defaults to today). It writes
nothing — weight is derived, never stored. The `SKILL.md` orchestration (ATSK-16) runs
it and hands the output to this reconcile step.
