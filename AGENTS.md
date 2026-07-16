# Atlas Skills — Agent Guide

Cross-harness guidance for agents working in this repo. `CLAUDE.md` is a symlink
to this file so Claude Code and Codex read the same instructions.

Atlas Skills is a small, standalone set of skills that run a coherent agent
**Session** against the **atlas vault**: assemble a Session Primer at the start,
memorialize the work at a boundary, and consolidate durable knowledge back into
the vault. Tasks are tracked in **Mimir** (the `mimir` CLI). See
[README.md](README.md) for the full picture.

## The vault

Everything is read from and written to the atlas vault at **`$ATLAS_PATH`** —
a required environment variable (there is no registry and no per-repo vault
config). A repo is an atlas workspace when it has an `.atlas.toml` binding
naming its `workspace`.

**norn is the vault-write authority.** Skills that create or mutate vault
documents route through the `norn` CLI (`norn new` / `norn set` / `norn edit`)
so frontmatter is schema-validated at write time — never hand-authored YAML.
Two invariants every documented command carries: pin the vault with
`-C "$ATLAS_PATH"` (norn resolves from `$NORN_ROOT`/cwd, never `ATLAS_PATH`),
and pass `--yes` (non-TTY runs are implicit dry-runs without it). Reads at
session start stay zero-dep: `build_primer.py` never requires norn.

## Testing

- **No external deps.** Tests use the stdlib `unittest` runner — there is **no
  pytest** in this project (don't reach for `python3 -m pytest`).
- **Run the suite:**

  ```bash
  python3 -m unittest discover -s tests
  ```

- Tests are hermetic: each builds a throwaway vault under a temp dir and points
  `build_primer.py` at it via `ATLAS_PATH`, so the real atlas vault is never
  touched.

## Running the primer

```bash
ATLAS_PATH=~/vaults/atlas python3 skills/start-session/build_primer.py
```

Resolves the `.atlas.toml` binding → `workspace`, merges the Active Context
(User Profile + Shared Memory + Workspace Brief), and folds in `mimir next` when
the repo has a `.mimir.toml` and `mimir` is on PATH. Prints
`ATLAS_UNINITIALIZED: …` if the repo isn't bound to a workspace.

## Editing skills

Skills live in `skills/` — one real directory. The eight: `start-session`,
`initialize-atlas`, `write-session-log`, `consolidate-workspace`,
`consolidate-memory`, `merged`, `watching-a-pr`, `shaping` — plus two alias
wrappers, `start` → `start-session` and `end` → `write-session-log`. Each keeps
whatever `resources/`, `references/`, and `templates/` it needs co-located
inside it, so the skill is self-contained wherever it's installed. They're
discovered by Claude Code and Codex, and installed cross-harness by the
`skills` CLI (`npx skills add …`) into `~/.agents/skills/`.

Parked skills live in top-level `pre-release/` — outside `skills/` because the
`skills` CLI discovers `SKILL.md` recursively under that tree, so anything
inside it would still be installed by `npx skills add --all`. See
[pre-release/README.md](pre-release/README.md).

## Keeping installed skills live

Installs land as **copies** under `~/.agents/skills/`, not symlinks back to this
repo — deliberately, so other sessions keep running the last-installed version
and never pick up mid-flight edits from a working tree. The cost is that a merge
isn't live until you re-copy.

So after the `merged` ritual pulls a PR into local `main`, refresh the
globally-installed copies so the merged changes go live:

```bash
npx skills add dbtlr/atlas-skills --all -g   # add/refresh all skills globally
# or, to update skills already installed:
npx skills update -g
```

`add --all` is the safe default — it also picks up newly added or renamed
skills, which `update` alone won't.
