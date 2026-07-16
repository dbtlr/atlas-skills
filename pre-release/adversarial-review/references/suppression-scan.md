# The suppression scan

A deterministic, model-free pass that catches **guardrail erosion** — one-line edits that weaken the safety envelope (disabled lint rules, type escapes, skipped tests, coverage pragmas) and that a model lens reading a long diff can miss. Grep cannot miss them.

Run it on every non-skipped review. Every hit is a **mandatory finding** that enters the resolution loop (SKILL.md Step 4) and ends in one of its terminal states. A hit is never a ban — it's a forced disposition.

## The scan

Two greps over the diff, added lines and removed lines — both are mandatory. Resolve `<main>` first: `git symbolic-ref --short refs/remotes/origin/HEAD`; if that errors (origin/HEAD unset — common in repos wired up with `git remote add` rather than cloned), run `git remote set-head origin --auto` and retry, or probe `git show-ref --verify refs/remotes/origin/main` (then `origin/master`).

**1. Added suppressions** — new lines that disable a guardrail:

```bash
git diff -U0 "$MAIN...HEAD" \
  | awk '/^\+\+\+ b\//{f=substr($0,7); next} /^\+\+\+ /{next} /^\+/{print f": "substr($0,2)}' \
  | grep -E 'eslint-disable|oxlint-disable|biome-ignore|@ts-ignore|@ts-nocheck|@ts-expect-error|as any|:[[:space:]]*any\b|prettier-ignore|#[[:space:]]*noqa|#[[:space:]]*type:[[:space:]]*ignore|#[[:space:]]*pragma:[[:space:]]*no cover|pylint:[[:space:]]*disable|#\[allow\(|#!\[allow\(|#\[ignore\b|//nolint|rubocop:disable|\.skip\(|\.only\(|\.todo\(|\bxit\(|\bxdescribe\(|\bxtest\(|@unittest\.skip|pytest\.mark\.(skip|xfail)|t\.Skip[A-Za-z]*\(|continue-on-error'
```

**2. Deleted assertions** — test lines that got weaker by removal:

```bash
git diff -U0 "$MAIN...HEAD" -- '*test*' '*spec*' \
  | awk '/^--- a\//{f=substr($0,7); next} /^--- /{next} /^-/{print f": "substr($0,2)}' \
  | grep -E '\b(assert|expect|should|require\.)|\.to[A-Z]'
```

Hits here need a matching *added* assertion nearby (moved/renamed test) — a deletion with no replacement is a narrowed suite and enters resolution as a finding.

Mechanics that are load-bearing — don't "simplify" them away:

- The awk header rules match the **full header forms** (`+++ b/…`, `--- a/…`, and the bare-prefix `+++ `/`--- ` for `/dev/null`), not just the prefix. A prefix-only exclusion silently drops real content lines that start with `++` or `--` (an added `++i; // eslint-disable-line` renders as `+++i;` in the diff; a deleted SQL comment renders as `--- …`).
- The output format is `file: line-content` — **not** file line numbers. When writing a hit into a finding record, locate the line in the file by its content; piping through `grep -n` would number the stream, not the file, and a wrong `file:line` in the disposition table sends the human to an unrelated line.

## Pattern list

Starter set, grouped by ecosystem. Extend it whenever a review discovers a suppression the scan missed — the list is maintained, not exhaustive. Patterns are deliberately loose (whitespace-tolerant, prefix-matched) — false positives cost one dismissal line; false negatives ship unreviewed erosion.

| Ecosystem | Patterns | Notes |
| --- | --- | --- |
| JS/TS lint | `eslint-disable` (all variants), `oxlint-disable`, `biome-ignore`, `prettier-ignore` | Config-file rule removals don't grep — but lint config files fail Q1 of the gate, so they're reviewed anyway |
| TS types | `@ts-ignore`, `@ts-nocheck`, `@ts-expect-error`, `as any`, `:any` / `: any` | `@ts-expect-error` is the legitimate form in type-assertion tests — still a finding, usually dismissed with that one-line reason |
| JS tests | `.skip(`, `.only(`, `.todo(`, `xit(`, `xdescribe(`, `xtest(` | `.only(` narrows the *whole suite* to one test — one of the sneakiest erosions |
| Python | `#noqa` / `# noqa`, `# type: ignore`, `# pragma: no cover`, `pylint: disable`, `@unittest.skip`, `pytest.mark.skip`, `pytest.mark.xfail` | |
| Rust | `#[allow(`, `#![allow(`, `#[ignore]` / `#[ignore = "…"]` | `#[allow(dead_code)]` during staged build-out is the classic legitimate deferral — defer with a task, don't dismiss silently |
| Go | `//nolint`, `t.Skip(`, `t.Skipf(`, `t.SkipNow(` | |
| Ruby | `rubocop:disable` | |
| CI | `continue-on-error` | A workflow that stops failing loudly is a dropped gate |

## Reading the results

- **Zero hits** — say so in one line and move on; the scan ran, that's the record.
- **Hits** — each becomes a finding with `failure_scenario` = the guardrail that no longer fires and what it would have caught. Fold them into the resolution loop alongside the engine's findings; they count in the trailer's `findings=` total.
