---
name: initialize-atlas
description: Bind this project to a vault Workspace and scaffold or self-heal it. Use when setting up atlas in a repo, when the user says "initialize my workspace", or when start-session reports no Project Binding (.atlas.toml).
argument-hint: "[workspace]"
---

# initialize-atlas

Bind a project to its vault **Workspace** and ensure that workspace is scaffolded correctly. Idempotent and self-healing — safe to run repeatedly.

> **Primary agent only.** If you were dispatched as a subagent, stop here.

## 1. Resolve the vault

The vault is always the **atlas vault**; its location is the `ATLAS_PATH` environment variable — there is no registry and no per-repo vault config.

- If `ATLAS_PATH` is set and the directory exists, use it as the vault root.
- If `ATLAS_PATH` is unset, ask the user to `export ATLAS_PATH=<their atlas vault root>` (offer `~/vaults/atlas` as the conventional default), then continue.

Scaffold the vault skeleton if missing (see `resources/vault-structure.md`):
- `.norn/config.yaml` — **norn is the vault-write authority** for the atlas skills (`write-session-log`, the consolidate pair all hard-require it), so the vault must carry a norn config. If `norn` isn't on PATH, stop and have the user install it. If the config is missing, seed it from `templates/norn-config.yaml` — the minimum schema contract the skills depend on (session-log flags, shared-profile types); an existing config is **never overwritten or merged** — leave it alone.
- `artifacts/session-logs/`, `artifacts/scratch/` (no `generated/` — specs/plans are transient, deleted on merge)
- `Workspaces/shared/` with `user.md` (User Profile), `memory.md` (Shared Memory), and `observations.md` (the observations ledger `consolidate-memory` extracts into). **Create each missing one through norn** so it carries its dedicated schema type from birth (`NOW=$(date +%Y-%m-%dT%H:%M)`):

  ```bash
  norn -C "$ATLAS_PATH" new "Workspaces/shared/user.md" \
    --field title="User Profile" --field description="<one line>" \
    --field type=user-profile --field workspace=shared \
    --field created="$NOW" --field modified="$NOW" --body-from-stdin --yes < <body>
  # memory.md → --field type=shared-memory; observations.md → --field type=observations
  ```

  Seed `user.md`/`memory.md` bodies lightly (a short user-profile interview can fill `user.md` later), each with the **above/below-the-line split**: a human-canon area, then a `---` rule, then the agent-consolidated region `consolidate-memory` maintains (above = hand-authored/pinned, never touched by the skill; below = weighted consolidation). `observations.md` starts as an empty ledger. If a legacy `partner_model.md` exists, offer to copy-and-curate it into `user.md` + `memory.md` rather than migrating in place.

## 2. Resolve the workspace name

- Use the `<workspace>` argument if given; else infer from the repo directory name and **confirm**.
- A Workspace maps 1:1 to a project, bound by name + path.

## 3. Elevator-pitch description

Get a 2–3 sentence description of the project, in priority order:
1. From an existing Workspace Brief (if re-initializing).
2. From the repo's `CLAUDE.md` / `AGENTS.md`.
3. Else scan the repo and infer one.

Confirm it with the user (offer to edit). It becomes the Brief's `description` and opening paragraph.

## 4. Scaffold / heal the workspace

Under `$ATLAS_PATH/Workspaces/<workspace>/`, ensure these exist — **create only what's missing; never overwrite existing content**:
- `<workspace>.md` — Workspace Brief. Compose the body from `templates/workspace-brief.md` (substitute `{{WORKSPACE}}`, `{{ELEVATOR_PITCH}}`), then create it through norn: `norn -C "$ATLAS_PATH" new "Workspaces/<workspace>/<workspace>.md" --field title=<workspace> --field description="<elevator pitch>" --field type=note --field kind=workspace --field workspace=<workspace> --field created="$NOW" --field modified="$NOW" --body-from-stdin --yes < <body>`. After creating it, stamp an initial `brief_baseline` into its frontmatter — its own scaffolded size — so a brand-new workspace starts within budget and `start-session` doesn't recommend a consolidation that has no logs to process. Measure it the same way `consolidate-workspace` does (code-point count, not `wc -m`): `python3 -c 'import pathlib,sys; print(len(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")))' "<brief path>"`, then stamp it with norn (pin the vault — norn resolves from `$NORN_ROOT`/cwd, never `ATLAS_PATH`): `norn -C "$ATLAS_PATH" set "Workspaces/<workspace>/<workspace>.md" --field-json brief_baseline=<chars> --yes` (an `unknown field` warning is benign). `consolidate-workspace` refreshes it on every groom thereafter.
- **The workspace enum in the norn config** — ensure `<workspace>` appears under `session-log-base` → `allowed_values` → `workspace` in `$ATLAS_PATH/.norn/config.yaml`; append it if missing. (The enum bounds the field, which doubles as norn's scan index for the consolidation queries; a workspace missing from it writes Session Logs that fail vault validation.) The config is a config file, not a vault document, so a direct anchored YAML edit is correct — then check it with `norn -C "$ATLAS_PATH" config validate`. **Append only, never remove or rename entries**: frozen logs carry every name that was ever bound, and removing one invalidates them retroactively.
- `glossary.md` — Generated by the `domain-modeling` skill (replaces `CONTEXT.md` if present). If that skill isn't installed, create a placeholder through norn (`norn -C "$ATLAS_PATH" new "Workspaces/<workspace>/glossary.md" --field title="Glossary" --field description="Domain terms for <workspace>" --field type=note --field kind=glossary --field workspace=<workspace> --field created="$NOW" --field modified="$NOW" --body-from-stdin --yes`) with a note to run `domain-modeling`.
- `decisions/`, `notes/`, `archive/`

> **Local override.** If the repo sets `decisions = "local"` (or a path) in `.atlas.toml`, scaffold `decisions/` + `glossary.md` at that in-repo target instead of in the vault workspace.

If everything already exists and is consistent, report: *"Your workspace is already initialized to `<full path>` and everything looks correct."* Otherwise apply only the missing pieces and say what you added.

## 5. Write the Project Binding

Write `.atlas.toml` at the repo root:
```toml
workspace = "<workspace>"
# decisions = "local"   # optional: keep decisions/glossary in-repo instead of the vault workspace
```
Ask whether to commit it to git (**default: no** — ensure it's in `.gitignore`).

## 6. Permissions (harness-specific)

Ensure the agent can read/write the vault paths. In Claude Code, add the vault globs to `.claude/settings.local.json`. Re-running `initialize-atlas` under a different harness adds that harness's needs.

## 7. Finish

- **Fresh init:** hand off to **start-session** to load the new context.
- **Heal:** just report what changed.
