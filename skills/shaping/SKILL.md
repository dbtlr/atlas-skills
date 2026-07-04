---
name: shaping
description: >-
  Use at the START of a half-baked idea — a new feature, service, refactor,
  migration, rewrite, re-platforming, technology switch, or other big
  cross-cutting change where the direction is rough and how it lands and how big
  it is aren't yet clear — to think it through, pressure-test it, and shape it
  toward a DECISION (which may be "no") plus a memorialized rationale and a
  phased plan, explicitly BEFORE any code. Signals: "let's think through", "talk
  it through before I commit", "is it worth it", "is this a good / dumb idea",
  "should we", "weigh the tradeoffs / what we'd gain and lose", "shape this",
  "explore whether we should…", "what would it look like if we…", "don't build
  anything yet", or considering / exploring / chewing-on a major shift — even if
  the user never says "shape". Distinguish by how settled the idea is: a CLEAR
  deliverable to turn into an implementation plan is brainstorming, not this; a
  roughly-known plan whose blind spots you want is grilling, not this; the fuzzy,
  earliest "is this even the right move, and how big is it" conversation is
  shaping. Output is shaped design documents — a design-of-record with a phased
  plan, plus a capability "asks" doc when the idea leans on another system —
  never code.
---

# Shaping

Shaping is the conversation that takes a big, vague, possibly-scary idea and pressure-tests it — to either a **shaped, de-risked, sequenced decision-of-record** or a clean, well-reasoned **"no"** — and memorializes the rationale, **without sliding into implementation**.

It is the **earliest** conversation in an idea's life: the idea is half-baked, you have a rough direction but not how it lands or how big it is, and you need help filling the gaps, finding which roads are worth going down, and making the idea *dramatically* better — or discovering the genuinely right direction. The win condition isn't just "a decision"; it's a decision arrived at by making the idea 100× better or realizing what the real move is.

The name and spirit come from Shape Up's *shaping*: the pre-betting work of making a raw idea solid enough to bet on (boundaries, rough size, risk) — deliberately *not* a spec. This skill extends that with two things shaping usually lacks: **feasibility grounded in the actual code and tools**, and **memorialized rationale as the deliverable**.

## What shaping is not — pick by how settled the idea is

The three pre-implementation conversations differ by **where the idea sits on the certainty spectrum**:

- **Brainstorming** — you have a **clear deliverable** and want to turn it into an implementation plan. (Highest certainty.)
- **Grilling** — you have a **decent idea of what you want to do** and need to find the edges: *what am I not seeing?* (Middle.)
- **Shaping** (this skill) — the idea is **half-baked**: a rough direction, but how it lands and how big it is aren't clear. The job is to fill the gaps, find which roads are worth going down, and make the idea dramatically better — or surface the genuinely right direction. (Lowest certainty, most generative.)

So: if there's already a clear thing to build → brainstorming. If the thing is roughly known and you want its blind spots → grilling. If you're at the *very start* and the shape and size are still fuzzy → shaping. It often generates large changes and may honestly end in "don't." Grilling is also a move you reach for *inside* shaping when a single fork needs hard interrogation; planning/spec-writing comes *after* shaping, if at all — a plan says *how to build*, shaping decides *what's worth building and in what shape*.

## The prime directive

**Hold the frame: discussion to a decision, not to code.** Name the deliverable as *understanding* at the very start — "the only thing that comes out of this is one or more notes / a decision." This single move keeps everyone in design space and prevents the slow leak into implementation. No code is written. No tasks are created until the decision is made and the human commits to building.

## The method

These are *moves*, not a rigid sequence. Read the conversation and reach for the one that fits. The art is choosing what to advance next.

1. **Advance one fork at a time; converge, don't enumerate.** Each turn, find the single most load-bearing open question, put a concrete proposal or reframe on it, and hand back. Resist the urge to resolve everything at once or to fire a checklist of questions — that's the brainstorm reflex, and it produces fatigue, not insight. A shaping conversation is a sequence of small, decisive increments.

2. **Crux-first.** Identify what the *whole idea rests on* and test that before any downstream detail. If the crux fails, nothing downstream matters; if it holds, the rest is shaping. Name it explicitly ("here's the single question this all rests on") so the human can confirm you're testing the right thing.

3. **Strawman → reframe → propagate.** Offer concrete proposals (a named option, a sample principle, a taxonomy) for the human to react against — most people reason far better against a concrete artifact than an open prompt. Expect "one-level-up" reframes: instead of picking from your menu, the human often replaces the frame with a generative principle. Treat that as the answer, stop pushing the old menu, and **propagate the new principle through the whole design**, not just the case that triggered it.

4. **Name generative principles as they crystallize.** When something settles, capture it as a *discriminator or principle*, not just an instance — a good principle predicts how later questions should resolve. ("X owns what's generic; Y owns what's domain-specific." "O(views), not O(nodes)." "Storage syntax is a service concern.") These named principles become the spine the rest of the conversation hangs on, and they're the most valuable thing to carry into the memorialized doc.

5. **Ground every load-bearing claim in reality — read, don't ask.** If a question can be answered by exploring — the code, the existing artifact or UI being changed, and (in an atlas workspace) the live `decisions/`, `glossary.md`, and docs — go read it instead of putting it to the human. Do not theorize feasibility. Read the actual docs and source; dispatch search agents for breadth; read the linchpin files yourself. When the question is "can system Z do this?", go find out — don't reassure from memory. **Correct yourself out loud when evidence overturns a claim** — that's not a failure, it's the method working, and it builds the trust the decision rests on. Interleave feasibility with design; don't defer all the checking to the end, because what you learn reshapes the design as you go.

6. **Triage ambiguity before committing.** Near the end, deliberately hunt the open questions and split them: **design-changing** (could alter the model — resolve *now*, out loud, with the human) versus **spec-at-phase** (mechanical — name them and defer). Ask the human directly: "any additional ambiguity?" The discipline is refusing to write the decision down until the design-changing forks have concrete answers.

7. **Hold the possibility of "no."** The job is to shape *or* to kill. Be adversarially honest, not an advocate — genuinely probe the premise, the cost, and the failure modes. A shaping conversation that *can't* end in "this is a bad bet" isn't shaping; it's selling. State the cost plainly and let the idea earn its keep.

8. **Hold the arc.** Track the spine of the exploration — where you are, what's settled, what's left — and at each hand-back, recommend the next increment while leaving the human to steer. You are keeping the through-line so they can think freely.

9. **Memorialize for the consumer, not as a transcript.** The durable output is shaped for *whoever uses it next* — a worklist with acceptance criteria for an implementer, an architecture-of-record for a future engineer, ask→get tests for another tool's author. Lift conclusions into their right home (a note, an ADR, a glossary term). A transcript dump is not a deliverable.

## Read the human's grain

Shaping is a conversation, so run it the way *this* human works — how much they want a recommendation versus a menu, how they signal a one-level-up reframe, how they pace. Don't assume a style; read it from how they engage, and adapt the moves above to fit.

Where the human's working style is already written down, use it rather than re-deriving it. **In an atlas workspace the Session Primer's User Profile carries exactly this** — durable facts about how the human reasons, decides, and communicates; read it and let it tune the conversation. Outside atlas, infer from the exchange itself and any project instructions, and adjust as the signals sharpen.

## The output artifacts

Shaping produces *named, durable design documents* — this is what makes a shaping session reusable rather than a one-off chat. There are two, plus two on-commit follow-ups. Fuller templates live in `references/artifacts.md` — read it when you're about to write a Shaping Doc or Asks Doc.

### Where the docs go

Don't make the human redirect you. **Discover the canonical home; don't assume one.** In order of preference:

1. **An atlas workspace.** If the repo is bound to an atlas vault — a `.atlas.toml` naming a `workspace`, vault at `$ATLAS_PATH` — route to the vault workspace the way the other atlas skills do: the **Shaping Doc → `Workspaces/<workspace>/notes/`**; the on-commit **ADR + glossary → through the `domain-modeling` skill** into the workspace `decisions/` and `glossary.md`; any **transient spec/plan → `artifacts/scratch/`** (deleted on merge — never the workspace). The **Asks Doc** goes to the *addressed* system's workspace when it too is an atlas workspace. **Create vault documents through norn** — `norn -C "$ATLAS_PATH" new "Workspaces/<workspace>/notes/<slug>.md" --field … --body-from-stdin --yes` — never a bare file write: norn pre-fills and validates the frontmatter schema at write time (pin the vault with `-C`; norn resolves from `$NORN_ROOT`/cwd, not `ATLAS_PATH`; `--yes` is required — non-TTY runs are dry-runs without it). (No atlas binding → skip to the generic homes below; shaping stands on its own in any repo — plain file writes are fine outside the vault.)
2. An **explicitly defined** docs/notes location — a project or workspace convention, a pointer in repo instructions (`CLAUDE.md` / `AGENTS.md` / similar), a configured docs path, or an obvious established home for this kind of doc.
3. An **existing conventional** directory in the project — `docs/`, `notes/`, a decisions/ADR dir — matching whichever the project already uses.
4. **Default to `docs/`** if nothing else is defined.

Write each artifact where *its consumer* will look. The Shaping Doc goes with the project being shaped; the Asks Doc goes with the *system it addresses* (a different repo or project may have its own canonical home). Only ask the human where to put it if it's genuinely ambiguous after looking — the point is to land it in the right place implicitly.

### 1. The Shaping Doc — the design-of-record *(always)*

The primary artifact: the architecture/decision-of-record. It is **durable knowledge** (the decision and its *why*), not a transient spec — it survives because the reasoning isn't recoverable from the eventual code. Write it to the canonical docs location (see *Where the docs go*). Recommended spine:

- **The decision** — one paragraph, plainly stated.
- **Why this is the right frame** — the crux, and why the obvious objection doesn't hold (or does).
- **The seam & principles** — the named generative principles that govern the design.
- **Structural / on-disk model** — if the idea has a concrete shape (schema, layout, interfaces).
- **Resolved forks** — each design-changing question with its settled answer (and the evidence).
- **Cost / value** — honest sizing, and which work is independently justified vs. irreducibly speculative.
- **Phased plan + sizing** — *the highest-value section for future scoping.* The sequence of mergeable, de-risked phases, what de-risks each, and where the sharp edges are. This is the part that gets re-referenced in every later scoping pass; make it standalone-useful.
- **Performance / risk model** — the governing rules and where the new risks live.
- **Spec-at-phase / open items** — the deferred mechanical questions, named so they aren't lost.
- **Cross-references & next step** — links to the asks doc, relevant decisions/ADRs, glossary terms; and what "commit to build" entails.

### 2. The Asks Doc — capability requirements / worklist *(conditional)*

Produce this **when the shaped idea depends on capabilities or changes from another system, tool, or team** you don't fully control within this design. It lives with *that system's* canonical docs (see *Where the docs go*) — where that system's authors will look — and doubles as their worklist and test fixtures. Shape each ask as **"ask → get"** acceptance criteria — *given this input, the call returns this* — so it's testable and buildable. Prioritize (P0 blocks / P1 parity / P2 has-a-workaround / Future), record the **current state** of each (present / partial / absent), and include a **"contract we depend on (don't break)"** section listing what already works that the design now relies on. Concrete query/usage scenarios make excellent test fixtures — include them.

### 3 & 4. On commit: ADR + glossary *(when the decision is taken)*

When the human commits to building, lift the irreducible decision into an **ADR** (it usually meets the test: hard-to-reverse, surprising, real trade-off), and fold any sharpened terms into the **glossary**. Then — and only then — groom the phased plan into actual work state / tasks. Shaping ends at the decision; execution is a separate act.

## Composition

Shaping is the *envelope*; it reaches for other skills as sub-moves:
- **grilling** when a single fork needs relentless interrogation.
- **frontend-design** when the idea is UI-flavored — pull design direction in rather than shaping the interface blind.
- **domain-modeling** when terms need pinning to a ubiquitous language.
- **documentation-and-adrs** at the memorialize step.
- **Explore / search subagents** for the feasibility grounding (move 5).

## Red flags (you're drifting out of shaping)

- You're writing code, or proposing to. → Stop; the deliverable is a decision.
- You're enumerating five questions at once. → Pick the one crux and advance it.
- You're defending a feasibility claim from memory. → Go read the source.
- You're advocating, not weighing. → Re-find the cost; let it earn "yes."
- You're dumping the transcript into a note. → Shape the doc for its consumer.
- You resolved nothing this turn. → Each increment should settle or sharpen something.
