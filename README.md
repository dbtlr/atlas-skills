# Atlas Skills

**A small set of skills for running a coherent agent session against the atlas vault.**
Atlas Skills teaches an agent to run a working **Session** — a body of work with a
single through-line, from session start to session log — backed by a markdown
knowledge vault and by **Mimir** for work tracking.

## The eight skills

| Skill | What it does |
| --- | --- |
| `start-session` | The entry point. Assembles the **Session Primer** (User Profile + Shared Memory + Workspace Brief, plus the `mimir next` work queue when present) and routes the work. |
| `initialize-atlas` | Binds a project to a vault Workspace and scaffolds or self-heals it. |
| `write-session-log` | At a work boundary, writes the merged **Session Log** memorializing what happened — decisions, deviations, and Consolidation Candidates. |
| `consolidate-workspace` | Consolidates the bound workspace's Session Logs — lifts durable knowledge into the workspace (Brief / decisions / notes) and follow-ups into Mimir, marks each log via norn, and grooms the Brief back to small. |
| `consolidate-memory` | (Global) regenerates the shared `user.md` / `memory.md` from user-observation candidates across **all** workspaces' Session Logs. The cross-project counterpart to `consolidate-workspace`. |
| `merged` | The post-merge ritual. After a PR is merged in GitHub, verifies the merge landed, returns to an up-to-date main, and deletes the finished branch/worktree. Composable args — `log` writes the Session Log, `next` picks up the next task (`log` always runs first). |
| `watching-a-pr` | The engagement loop around an open PR: arms a stateless background watcher (`pr_watcher.py`), then on each wake routes the batch it returns — addresses inline review comments, fixes red CI, announces green — and re-arms, until the PR merges (runs the `merged` cleanup + reconciles stragglers) or the watch times out. Vault-independent. |
| `shaping` | The earliest design conversation: pressure-tests a half-baked idea to a decision-of-record (or a clean "no") and memorializes the rationale — **before any code**. Atlas-aware (Shaping Doc → the workspace `notes/`, on-commit ADR + glossary via `domain-modeling`), with a generic `docs/` fallback so it stands on its own in any repo. |

Two typing-saver aliases install alongside them: **`/start`** → `start-session`
and **`/end`** → `write-session-log`. They're thin wrappers, not additional
skills — user-invoked only in Claude Code (`disable-model-invocation`); on other
harnesses they simply redirect to the real skill.

## Requirements

- **`ATLAS_PATH`** — set this to your atlas vault root (e.g. `export ATLAS_PATH=~/vaults/atlas`). The skills read and write the vault there; the vault is always the atlas vault.
- **Python 3.11+** for `build_primer.py` (stdlib `tomllib`), or the `tomli` package on older interpreters.
- **Mimir** (optional) — the `mimir` CLI, for repos that track work in Mimir. When a repo has a `.mimir.toml`, the primer folds `mimir next` into the Session Primer.
- **GitHub CLI** (`gh`, authenticated) — for the `merged` skill, which verifies a PR actually merged before deleting anything.

## Install

These are plain skills — no plugin. Install them cross-harness with the `skills`
CLI, which fetches from GitHub and symlinks into `~/.agents/skills/` (read by
Claude Code, Codex, Cursor, Gemini CLI, opencode, and others):

```bash
npx skills add dbtlr/atlas-skills --skill '*'
```

Refresh an existing install after changes:

```bash
npx skills update start-session initialize-atlas write-session-log consolidate-workspace consolidate-memory merged watching-a-pr shaping start end -g -y
```

Once installed, a primary session starts with:

```
/start-session
```

(or its shorthand, `/start`)

`start-session` is also the recovery point after a context clear/reset: it
reloads the Session Primer for the same body of work before the agent continues.

## How it fits together

A **Session** is bounded by a body of work, not by a single context window.
`start-session` builds the Session Primer that re-loads on each resumption,
keeping the through-line across compactions and new windows. At a work boundary,
`write-session-log` freezes what happened; `consolidate-workspace` later lifts a
workspace's durable parts into maintained context, and `consolidate-memory` folds
user observations into the shared profile. `initialize-atlas` keeps the underlying
Workspace well-formed.

## Repository layout

- `skills/` — the eight released skill sources, each self-contained (any `build_primer.py`, `resources/`, `references/`, `templates/` it needs co-located inside it).
- `skills/start-session/build_primer.py` — resolves the `.atlas.toml` binding and `$ATLAS_PATH` into the merged Active Context, folding in `mimir next` when present.
- `pre-release/` — skills parked outside the install path (the `skills` CLI discovers `SKILL.md` recursively under `skills/`, so disabled skills must live outside that tree). See [pre-release/README.md](pre-release/README.md).
- `tests/` — primer-merge and hook tests (stdlib `unittest`).

## License

MIT — see [LICENSE](LICENSE).
