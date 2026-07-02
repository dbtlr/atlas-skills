---
name: adversarial-review
description: "The verification gate before a change is declared complete — MANDATORY before creating a PR (`gh pr create`) on any work branch, and on request ('run the review', 'adversarial review'). Runs the proportionality gate (or declares a skip), a deterministic suppression scan, delegates the review to the harness's native engine, then drives the resolution loop until every finding is fixed, dismissed with a stated reason, or deferred to a tracked task — recording the disposition trailer and presenting the table to a human. Primary agent / controller only."
---

# adversarial-review

Work is **not complete until it is verified** — by an adversarial agent, presented to a human. This skill turns that rule into a deterministic procedure. It has two halves with different owners: the **review engine** (fresh-context finders and verifiers — delegated to the harness, never re-implemented here) and the **resolution loop** (what happens to the findings — owned by this skill, non-negotiable).

> **Primary agent / controller only.** The controller owns verification and disposition. A subagent that built something reports back; it never runs its own completion gate.

<EXTREMELY-IMPORTANT>
If you are about to create a PR, or about to tell the user a change is finished, and no adversarial review has run against the branch's **current** shape, STOP and run this skill first. These thoughts mean you are rationalizing:

| Thought | Reality |
| --- | --- |
| "The tests are green" | Green tests are a precondition of review, not a substitute. The review this skill was distilled from found two confirmed bugs sitting in a fully green 660-test suite. |
| "It's a tiny diff" | Those two bugs lived in a ~150-line diff. Small is not safe; the gate decides the tier, not you. |
| "I reviewed it carefully while writing it" | You re-derive your own blind spots. Adversarial means fresh contexts — none carry your session. |
| "The user is waiting; I'll review after the PR" | The PR **is** the "declaring it done" moment. After never comes. |
| "It's just a refactor / just docs" | Then say so on the record: run the proportionality gate and let it declare the skip. Silent skips are forbidden, declared ones are one line. |
| "I'll note the findings and move on" | "Noted" is not a terminal state. Every finding ends fixed, dismissed-with-reason, or deferred-to-a-tracked-task. |
</EXTREMELY-IMPORTANT>

## Preconditions

Review is the **last** gate before submit, not a substitute for the earlier ones. Before running it:

- The change is complete and green — build, lint, tests, and any configured verify have passed; a smoke has run if the change has a runtime surface.
- The diff is **committed on a branch**, so the review target is immutable: `git diff <main>...HEAD`, where `<main>` is resolved, never assumed: `git symbolic-ref --short refs/remotes/origin/HEAD` — and if that errors (origin/HEAD unset, common in repos wired up with `git remote add`), run `git remote set-head origin --auto` and retry, or probe `git show-ref --verify refs/remotes/origin/main` (then `origin/master`).

If a precondition fails, finish it first — findings against a half-built change waste the whole fan-out.

## Step 1 — The proportionality gate

Two questions, in order. The output is a tier or a declared skip — never silence.

**Q1: Did anything that executes — or gates what executes — change?**

If no → **skip, declared**: write the skip trailer (below) and stop. The skip class is deliberately narrow: `docs-only`, `comments-only`, `formatting-only` — where `formatting-only` means the diff is the output of the project's configured formatter with no manual edits; the formatter's behavior-preservation guarantee is what earns the skip. If qualifying for a skip needs an argument, the answer is no-skip. A lockfile or dependency bump is **never** a skip — it changes which code executes (supply-chain swaps included); it reviews at `low`. Tests, CI/workflow config, lint config, and suppression comments likewise sit on the **review** side of this line — a weakened test or a disabled rule is a dropped guardrail, the exact failure class this gate exists to catch.

**Q2: What is the blast radius?** Pick the engine tier:

| Diff character | Tier |
| --- | --- |
| Mechanical + leaf: rename, copy change, single-file fix with an obvious trigger; tests-only; CI-config-only; lockfile/dependency-bump-only | `low` |
| New behavior, multi-file, or **any deletion/replacement of existing logic** | `high` — the default |
| Shared infrastructure, data model/migration, security-adjacent, or the change claims an invariant whose failure would be **costly or hard to reverse** — corrupted data, a crossed security boundary, wrong behavior shipping silently | `max` |

**Doubt rounds up.** Between two tiers, take the higher — but **escalation is earned by the blast radius of the claim failing, not by the claim's phrasing.** A change whose claim sounds absolute ("this can no longer happen") but which *fails cheap and loud* — enforcement, tooling, a fail-open guard where a bypass costs one recoverable, visible mistake — reviews at `high`, not `max`. Reserve `max` for where a false claim corrupts data, crosses a security boundary, or ships wrong behavior silently.

**Size caps width.** The tier sets *depth*; the diff's *size* caps how wide the fan-out should go. Lens partitioning across many agents exists to beat per-lens attention saturation — which doesn't happen on a small surface, where a few strong reviewers exhaust the findings and extra agents just re-read the same lines. So on a diff under ~200 changed lines, cap at `high` even when character argues for `max`; under ~50 lines mechanical, `low` is usually enough. Widen for large diffs, not small ones — model tier stays strong (a review is not the place to economize on model quality), but agent *count* scales with surface area, not with how alarming the change sounds. On the native engine this means picking a lower effort tier for a small diff; on the fallback ([references/fallback-engine.md](references/fallback-engine.md)) it sets the finder count directly.

**Re-review is this same gate, re-applied to the delta.** After follow-up work on an already-reviewed branch, run Q1/Q2 against the diff since the last review: "changed a sentence of copy" → no re-review; "moved files and re-composed functions" → amended review at the tier the delta earns. An amended review appends a new trailer; the latest trailer on the branch is the one that counts.

## Step 2 — The suppression scan (deterministic, model-free)

On every non-skipped review, run **both scans** in [references/suppression-scan.md](references/suppression-scan.md) — exact commands there: grep the **added lines** of the diff for suppression patterns, and grep the **deleted lines** of test files for removed assertions. This hunts **guardrail erosion**: disabled lint rules, type escapes (`as any`, `@ts-ignore`), skipped or narrowed tests (`.skip`, `.only`), coverage pragmas, `#[allow(…)]`. These are one line each; a model lens reading a long diff can miss them, grep cannot.

**A hit is a mandatory finding, not a ban.** Legitimate escapes exist (`@ts-expect-error` on a test asserting a type error; `#[allow(dead_code)]` during staged build-out). Every hit enters the resolution loop and ends in a terminal state like any other finding — removed (fixed), justified on the record (dismissed), or tracked (deferred). The agent that sneaks in an `as any` isn't blocked; it's forced to say so in the PR body.

## Step 3 — Run the engine

Select by harness self-identity (the first line of your system prompt):

| Harness | Engine |
| --- | --- |
| Claude Code | Invoke the `/code-review` skill at the gate's tier (`low` / `high` / `max` effort) |
| Codex | `/review` is user-invoked — the model cannot trigger it. Ask the user to run it (a request worded "review changes on `<branch>` against `<base>`" routes to it); if no user is available, drop to the fallback engine by capability (below) |
| Anything else | Subagents available → **fallback**; none → **inline** — both specified in [references/fallback-engine.md](references/fallback-engine.md) |

Rules that hold for every engine:

- Reviewers see the **committed diff**, in **fresh contexts** — none carry the builder's session. Freshness is the property that makes the review adversarial rather than confirmatory.
- Reviewers inherit the session model. A review is exactly the place not to economize.
- Every finding must arrive as a claim plus evidence: `{file, line, summary, failure_scenario}` with a verdict (`CONFIRMED` — inputs and wrong output named; `PLAUSIBLE` — real mechanism, uncertain trigger). Agents hand each other claims plus evidence, never conclusions alone.

**Fallbacks** (no native engine) — the controller runs the review itself, at the same contract (verdict ladder, JSON record shape). With subagents it's a compressed fresh-context fan-out (**fallback**) — size-scaled finder counts, verifier grouping, deterministic assembly; with none it's an honest single-context sequential pass (**inline**), weaker and said so. Both are specified — prompts and all — in [references/fallback-engine.md](references/fallback-engine.md). The **Codex** row above also drops here when no user is available to run `/review`.

## Step 4 — The resolution loop

The half agents cut corners on. Work every finding, in severity order:

1. **Re-derive before accepting.** Trace each finding against the actual code — the reviewer's claim is input, not verdict. While tracing, look across findings for a **shared root cause**: several findings often want one fix at a different altitude, which no individual finding states.
2. **Dispose of every finding into exactly one terminal state:**
   - **Fixed** — with proof per the ladder below.
   - **Dismissed** — with the refuting argument stated on the record, held to the verifier's own evidentiary bar (cite the line, the invariant, or the bounded consumer set). Only `PLAUSIBLE` findings may be dismissed; a `CONFIRMED` correctness finding in the new code is never dismissible or deferrable.
   - **Deferred** — to a tracked task **created now, not promised**, when the defer rubric below passes.
3. **Prove fixes per the proof ladder** — the obligation lives in the medium where the failure lives:

   | Finding class | Obligation |
   | --- | --- |
   | Behavioral (wrong output, crash, data loss) | Regression test encoding the failure scenario — written first, **observed red**, then green. Mandatory. A behavioral CONFIRMED that resists a failing test goes back to re-derivation — the resistance is evidence about the finding. |
   | Observable but costly (perf, races, env-dependent) | Reproduce if cheap to scaffold; if genuinely expensive, fix with the mechanism stated on the record, or defer via the rubric. Judgment is allowed here and only here. |
   | Non-executable (doc drift, suppression hits, conventions) | The diff is the proof — no test theater. These are cheap: default fix-now. |

4. **Re-run every earlier gate the fixes may have invalidated** — full verify, fresh smoke. A fix that changes shape can awaken exactly the failures the review predicted.
5. **Record and present** (next section). Only then may "done" be declared.

**The defer rubric.** Fix now unless **all** of these hold:

1. Not a correctness regression this change introduces (pre-existing bugs the diff merely exposes may defer as their own task).
2. Not load-bearing for the change's own claim — if the PR says "X can no longer happen" and the finding is a way to make X happen, it's in-scope by definition, however exotic the path.
3. The blast radius is bounded and known — you can state precisely who hits it and when. "Probably rare" without a mechanism is not bounded.
4. Deferring doesn't compound — the follow-up won't be materially harder after this merges (no schema/contract/migration entrenchment, nothing about to build on the flawed shape).
5. It has a durable home **before submit** — the tracked task exists now. Not worth a task → it's worth fixing now or dismissing outright; say which.

A deferral justified by "the fix is tedious" is not a deferral; it's a skipped gate.

| Thought | Reality |
| --- | --- |
| "I'll note this one for later" | Not a terminal state. Fix it, dismiss it with a reason, or create the task now. |
| "The reviewer is probably wrong" | Then prove it — dismissal holds the same evidentiary bar as the verdict it overturns. |
| "I'll file the follow-up task after the PR is up" | "After" is a promise, not a record. The task exists before the trailer is written. |
| "A failing test is awkward to scaffold here" | For behavioral findings that's the mandatory rung — and if it truly can't fail, re-derive the finding. |
| "The fix is small; no need to re-run the suite" | Small fixes invalidate gates too. Re-run what the fix could have touched. |

## Step 5 — The disposition record

One source of truth, two forms.

**The trailer** — machine-checkable, greppable by enforcement hooks (`git log <main>..HEAD`). Exact grammar, one line, two forms:

```
Adversarial-Review: run engine=<engine> tier=<low|high|max> findings=<N> fixed=<N> dismissed=<N> deferred=<N>[(<TASK-ID>[,<TASK-ID>…])]
Adversarial-Review: skipped reason=<docs-only|comments-only|formatting-only>
```

- `engine` ∈ `code-review` | `review` | `fallback` | `inline`. Engine and tier are orthogonal: `engine` names the machinery, `tier=` records the gate's output whatever the machinery — a `max`-tier fallback review is `engine=fallback tier=max`.
- `findings` counts survivors reaching resolution (engine findings + suppression hits); `fixed + dismissed + deferred = findings`.
- Every deferral names its task id in the parens — that's the audit trail.
- The trailer rides the commit that closes the review: the fix commit when there is one, otherwise an empty record commit (`git commit --allow-empty`). Never amend pushed commits. Multiple trailers on a branch are fine (amended reviews append); **the latest wins**.

**The disposition table** — human-readable, delivered in chat *and* in the PR body:

```markdown
| # | Finding (file:line) | Verdict | Disposition |
| --- | --- | --- | --- |
| 1 | Archive bypass writes cycle (store.rs:214) | CONFIRMED | Fixed — regression test `test_unarchive_rejects_cycle` (red→green) |
| 2 | Guard belongs at shared seam (edges.rs:88) | PLAUSIBLE | Dismissed — the helper IS the seam; only two verbs write edges |
| 3 | Unarchive skips cycle check | PLAUSIBLE | Deferred → TASK-123 (bounded: pre-guard legacy data only) |
```

Presenting this table to the human is the skill's terminal act — the "presented to a human" half of the rule. **"Done" may be declared only after the table is presented.**

## Enforcement (optional hardening)

On harnesses with hooks, a PreToolUse hook on `gh pr create` can grep the branch for the trailer and block PR creation when it's absent — catching the common forgotten-gate case (an agent about to open a PR without having run the review). It's a speed bump, not an adversarial boundary: a fail-open hook can't stop deliberate evasion, and doesn't try. The hook and its install doc live in [resources/hooks/](resources/hooks/README.md); the skill is complete without it — the trailer convention is the contract, the hook just makes the common miss loud.
