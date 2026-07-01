# Atlas Skills

**A small set of skills for running a coherent agent session against the atlas vault.**
Atlas Skills teaches an agent to run a working **Session** — a body of work with a
single through-line, from session start to session log — backed by a markdown
knowledge vault and by **Mimir** for work tracking.

## The four skills

| Skill | What it does |
| --- | --- |
| `start-session` | The entry point. Assembles the **Session Primer** (User Profile + Shared Memory + Workspace Brief, plus the `mimir next` work queue when present) and routes the work. |
| `initialize-atlas` | Binds a project to a vault Workspace and scaffolds or self-heals it. |
| `write-session-log` | At a work boundary, writes the merged **Session Log** memorializing what happened — decisions, deviations, and Consolidation Candidates. |
| `consolidate-sessions` | Lifts Consolidation Candidates out of frozen Session Logs into maintained context — durable knowledge to the workspace, follow-ups to Mimir, user observations to the shared profile. |

## Requirements

- **`ATLAS_PATH`** — set this to your atlas vault root (e.g. `export ATLAS_PATH=~/vaults/atlas`). The skills read and write the vault there; the vault is always the atlas vault.
- **Python 3.11+** for `build_primer.py` (stdlib `tomllib`), or the `tomli` package on older interpreters.
- **Mimir** (optional) — the `mimir` CLI, for repos that track work in Mimir. When a repo has a `.mimir.toml`, the primer folds `mimir next` into the Session Primer.

## Install

These are plain skills — no plugin. Install them cross-harness with the `skills`
CLI, which fetches from GitHub and symlinks into `~/.agents/skills/` (read by
Claude Code, Codex, Cursor, Gemini CLI, opencode, and others):

```bash
npx skills add dbtlr/atlas-skills --skill '*'
```

Refresh an existing install after changes:

```bash
npx skills update start-session initialize-atlas write-session-log consolidate-sessions -g -y
```

Once installed, a primary session starts with:

```
/start-session
```

`start-session` is also the recovery point after a context clear/reset: it
reloads the Session Primer for the same body of work before the agent continues.

## How it fits together

A **Session** is bounded by a body of work, not by a single context window.
`start-session` builds the Session Primer that re-loads on each resumption,
keeping the through-line across compactions and new windows. At a work boundary,
`write-session-log` freezes what happened; `consolidate-sessions` later lifts the
durable parts into maintained context. `initialize-atlas` keeps the underlying
Workspace well-formed.

## Repository layout

- `skills/` — the four skill sources, each self-contained (its `build_primer.py`, `resources/`, `references/`, `templates/` co-located inside it).
- `skills/start-session/build_primer.py` — resolves the `.atlas.toml` binding and `$ATLAS_PATH` into the merged Active Context, folding in `mimir next` when present.
- `tests/` — primer-merge tests (stdlib `unittest`).

## License

MIT — see [LICENSE](LICENSE).
