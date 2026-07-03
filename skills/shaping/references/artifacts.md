# Shaping artifacts — templates

Fuller skeletons for the two shaping documents. Read this when you're about to write one. Adapt the sections to the idea — these are spines, not forms to fill in mechanically. Drop sections that don't apply; never pad. Write where the canonical docs live (see SKILL.md → *Where the docs go*).

- [Shaping Doc](#shaping-doc) — the design-of-record (always)
- [Asks Doc](#asks-doc) — capability requirements for another system (conditional)
- [Principles for both](#principles-for-both)

---

## Shaping Doc

The design-of-record: the decision and its *why*. Durable knowledge — write it for a future engineer who wasn't in the room and will never see the conversation. Lead with a short status/framing banner so a reader knows its maturity (discussion / go-lean / committed) and where the companion docs are.

```markdown
# <Idea> — <Refactor / Adoption / Direction> Design

> **Status:** <design discussion | go-lean | committed>. <One line on what this is and
> isn't.> When committed, lift the core decision into an ADR. Companion: <link to Asks Doc>.

## The decision
<One paragraph. State it plainly — what changes, and what the new shape is.>

## Why this is the right frame
<The crux: what the whole idea rests on, and why the obvious objection doesn't hold
(or, honestly, where it does). If the idea looks like a reversal of a prior decision,
show why it isn't — name what actually changed. This is the most-scrutinized section;
make the reasoning airtight.>

## The seam & principles
<The named generative principles that govern the design — the discriminators that
predict how future questions resolve. Who owns what. The boundaries. These are the
spine; state them as reusable rules, not as the instances that produced them.>

## Structural / on-disk model        (if the idea has a concrete shape)
<Schema, layout, interfaces, data model. Tables/lists over prose where it's structural.>

## Resolved forks
<Each design-changing question that came up, with its settled answer AND the evidence
that settled it. "We chose X because <verified fact>." Future readers will re-litigate
anything left unjustified.>

## Cost / value
<Honest sizing. Crucially: separate work that is independently justified (worth doing
regardless of this decision) from the irreducibly speculative slice. This reframes
"huge effort, no new features" objections by showing how little is actually a bet.>

## Phased plan + sizing               ← highest-value section for future scoping
<The sequence of mergeable, de-risked phases. For each: what it delivers, what de-risks
it, rough size, and the sharp edges. Prefer incremental-behind-a-seam over a long-lived
parallel branch. Name the early de-risking wedge (the low-risk slice that proves the
approach). Make this section standalone-useful — it gets re-referenced in every later
scoping pass, often without the rest of the doc.>

## Performance / risk model           (if relevant)
<The governing rules (e.g. complexity bounds, invariants) and where the *new* risks
live. Distinguish risks that are prevented by the architecture from those that need
active mitigation.>

## Spec-at-phase / open items
<The mechanical questions deliberately deferred — named so they aren't lost, with a
one-line note on each so the phase that owns it can pick it up.>

## Cross-references & next step
<Links to the Asks Doc, relevant decisions/ADRs, glossary terms. Then: what "commit to
build" entails (ADR + grooming the plan into work state). Shaping ends at the decision.>
```

---

## Asks Doc

Produce only when the shaped idea **depends on another system/tool/team**. It's a requirements doc *and* that system's worklist *and* its test fixtures. The unifying device is **ask → get**: every ask is written as an acceptance criterion (*given this input, the call returns this*), so it's testable and buildable.

```markdown
# <This system> on <That system> — Capability Asks for <That system>

## Context
<Why these asks exist — the shaped idea, in a paragraph, and the headline feasibility
read (e.g. "~90% already exists; the real build list is small").>

## Design values to preserve
<Any cross-cutting principles the consumer must honor (the seam, what stays whose job).>

## Legend
<State + priority conventions: PRESENT / PARTIAL / ABSENT; P0 blocks / P1 parity /
P2 has-a-workaround / Future. Each ask is "Ask → Get".>

## A. Contract we depend on (confirmed PRESENT — do not break)
<What already works that the design now relies on. This protects the consumer from
breaking you, and tells them what NOT to build. Verify each against their docs/source.>

## B…N. The asks (grouped: query / write / rules / scale / …)
<Per ask:
  - Name · area · priority · state.
  - Why it's needed (the concrete use case).
  - **Ask → Get:** given <input/vault state>, <command/call> returns <result>.
  - Scope guidance / fallback that works today.>

## Query / usage scenarios (test fixtures)        ← high value
<The concrete workloads the consumer will face, each with the exact call, expected
output, and — powerfully — the inefficiency in the *current* implementation it cures.
These double as acceptance tests the other team can build against.>

## Out of scope (no ask)
<What you explicitly are NOT asking for, so the consumer doesn't over-build.>

## Priority summary
<A table, most-blocking first, plus a one-paragraph "what's P0 vs P1 and why."
State plainly if nothing is P0 — i.e. every gap has a working fallback.>
```

---

## Principles for both

- **Memorialize for the consumer, not as a transcript.** The Shaping Doc serves a future engineer; the Asks Doc serves another tool's author. Shape each for its reader.
- **Ground claims; cite where you verified.** "Confirmed against `<file>`/`<doc>`" is worth more than an assertion. If you self-corrected during shaping, the doc carries the *corrected* conclusion.
- **Name the principles, not just the instances.** The reusable value is the discriminator ("X owns generic, Y owns domain-specific"), not the example that produced it.
- **Phased plan is the reusable core.** It's the section future scoping leans on; make it survive being read alone.
- **Link the pair.** Shaping Doc ↔ Asks Doc cross-reference each other; both link to the decisions/ADRs/terms they touch.
- **Cross-system asks live with the system they address**, not with the originating project.
