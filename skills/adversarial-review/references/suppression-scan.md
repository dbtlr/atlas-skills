# The suppression scan

A deterministic, model-free pass that catches **guardrail erosion** — one-line edits that weaken the safety envelope (disabled lint rules, type escapes, skipped tests, coverage pragmas) and that a model lens reading a long diff can miss. Grep cannot miss them.

Run it on every non-skipped review. Every hit is a **mandatory finding** that enters the resolution loop: removed (fixed), justified on the record (dismissed), or tracked (deferred). A hit is never a ban — it's a forced disposition.

## The scan

Two greps over the diff, added lines and removed lines. Resolve `<main>` first (`git symbolic-ref --short refs/remotes/origin/HEAD`).

**1. Added suppressions** — new lines that disable a guardrail:

```bash
git diff -U0 "$MAIN...HEAD" \
  | awk '/^\+\+\+ /{f=substr($2,3)} /^\+/ && !/^\+\+\+/ {print f": "substr($0,2)}' \
  | grep -nE 'eslint-disable|oxlint-disable|biome-ignore|@ts-ignore|@ts-nocheck|@ts-expect-error|as any|: any\b|prettier-ignore|# noqa|# type: ignore|# pragma: no cover|pylint: disable|#\[allow\(|#!\[allow\(|#\[ignore\]|//nolint|rubocop:disable|\.skip\(|\.only\(|\.todo\(|\bxit\(|\bxdescribe\(|\bxtest\(|@unittest\.skip|pytest\.mark\.(skip|xfail)|t\.Skip\(|continue-on-error'
```

**2. Deleted assertions** — test lines that got weaker by removal:

```bash
git diff -U0 "$MAIN...HEAD" -- '*test*' '*spec*' '*_test.*' '*.test.*' \
  | awk '/^--- /{f=substr($2,3)} /^-/ && !/^---/ {print f": "substr($0,2)}' \
  | grep -nE '\b(assert|expect|should|require\.)|\.to[A-Z]'
```

Hits here need a matching *added* assertion nearby (moved/renamed test) — a deletion with no replacement is a narrowed suite and enters resolution as a finding.

## Pattern list

Starter set, grouped by ecosystem. Extend it whenever a review discovers a suppression the scan missed — the list is maintained, not exhaustive.

| Ecosystem | Patterns | Notes |
| --- | --- | --- |
| JS/TS lint | `eslint-disable` (all variants), `oxlint-disable`, `biome-ignore`, `prettier-ignore` | Config-file rule removals don't grep — but lint config files fail Q1 of the gate, so they're reviewed anyway |
| TS types | `@ts-ignore`, `@ts-nocheck`, `@ts-expect-error`, `as any`, `: any` | `@ts-expect-error` is the legitimate form in type-assertion tests — still a finding, usually dismissed with that one-line reason |
| JS tests | `.skip(`, `.only(`, `.todo(`, `xit(`, `xdescribe(`, `xtest(` | `.only(` narrows the *whole suite* to one test — one of the sneakiest erosions |
| Python | `# noqa`, `# type: ignore`, `# pragma: no cover`, `pylint: disable`, `@unittest.skip`, `pytest.mark.skip`, `pytest.mark.xfail` | |
| Rust | `#[allow(`, `#![allow(`, `#[ignore]` | `#[allow(dead_code)]` during staged build-out is the classic legitimate deferral — defer with a task, don't dismiss silently |
| Go | `//nolint`, `t.Skip(` | |
| Ruby | `rubocop:disable` | |
| CI | `continue-on-error` | A workflow that stops failing loudly is a dropped gate |

## Reading the results

- **Zero hits** — say so in one line and move on; the scan ran, that's the record.
- **Hits** — each becomes a finding with `failure_scenario` = the guardrail that no longer fires and what it would have caught. Fold them into the resolution loop alongside the engine's findings; they count in the trailer's `findings=` total.
