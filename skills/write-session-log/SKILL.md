---
name: write-session-log
description: Write the merged Session Log that memorializes a Session — what happened, decisions, deviations, and Consolidation Candidates. Trigger at a work boundary — a task/feature/investigation finished, a wrap-up signal, context nearing compaction, or an explicit request. Primary agent only.
---

# write-session-log

Memorialize the current **Session** as one frozen record, centered on **Consolidation Candidates** — the narrative of the work plus the user observations worth carrying forward, in a single log.

> **Primary agent only.** Subagents never write Session Logs.

## When to trigger

At a work boundary — don't wait to be asked:
- a task / feature / fix / investigation finished
- the user signals wrap-up ("that's all", "good session", "done for now")
- context is approaching compaction (write *before* the threshold, not after)
- a repo switch, or an explicit request ("write a session log")

## Preflight — norn is required

The log is created **through norn**, so its frontmatter is schema-validated at write time (norn's `session-log-base` rule) instead of hand-authored — no fallback:

```bash
command -v norn || { echo "write-session-log requires the 'norn' CLI on PATH. Install it and re-run."; exit 1; }
[ -n "$ATLAS_PATH" ] && [ -f "$ATLAS_PATH/.norn/config.yaml" ] || { echo "write-session-log needs ATLAS_PATH set to the atlas vault root (the dir containing .norn/config.yaml)."; exit 1; }
```

If either check fails, stop and tell the user — don't hand-write the file; an unvalidated log is invisible to (or breaks) the consolidation scans downstream.

## What to write

Compose the log body from `templates/session-log.md` — it is the body outline; frontmatter is norn's job (below). Fill every section; more detail is better than less — write for a future session with zero memory of today.

The heart is **Consolidation Candidates** — *"what happened that, had I known it earlier, would have saved time?"* Tag each by the taxonomy in `references/consolidation-candidates.md`:
- **Durable knowledge** — decisions, user-personas, user-stories
- **Future opportunities** — tech-debt, follow-up-tasks, open-questions
- **User observations** — collaboration-patterns

**Mark carried candidates.** If a candidate repeats one a prior Session Log raised that was never actioned, list it as `carried (since <YYYY-MM-DD>)` (the first-raised date, optionally a count) rather than as fresh — see *Carried candidates* in `references/consolidation-candidates.md`. This is detection only: you surface the recurrence, you don't file or decide it (that's `consolidate-workspace`' job).

## Create it with norn

The log lives at `artifacts/session-logs/<YYYY-MM-DD-HHMM>-<slug>.md` — vault-root `artifacts/`, **never inside the workspace**. Use an accurate timestamp (`date "+%Y-%m-%d %H:%M"`) — never invent one. Write the composed body to a temp file, then create the log in one call — **pin the vault with `-C "$ATLAS_PATH"`** (norn resolves its vault from `$NORN_ROOT`/cwd, never from `ATLAS_PATH`; run from a repo cwd, a bare call hits the wrong place):

```bash
norn -C "$ATLAS_PATH" new "artifacts/session-logs/<YYYY-MM-DD-HHMM>-<slug>.md" \
  --field title="<session title>" \
  --field description="<one-line summary>" \
  --field type=session-log --field-json kind=null \
  --field workspace=<workspace> \
  --field created="<YYYY-MM-DDTHH:MM>" --field modified="<YYYY-MM-DDTHH:MM>" \
  --field-json workspace_consolidated=false --field-json memory_consolidated=false \
  --body-from-stdin --yes < <body temp file>
```

`--yes` is load-bearing: without it a non-TTY run is an implicit dry-run and **nothing is written**. norn validates the new doc on write — treat any warning it emits as a finding to fix now, not noise.

The two consolidation-state flags start `false` and **stay false here**: they're the cursor `consolidate-workspace` / `consolidate-memory` scan on (`norn find`) and flip (`norn set`) once each has lifted this log's candidates.

## After writing

- Update the Workspace Brief's session-state sections (Current State, What's Next, Open Questions, Learnings, Recent Sessions) — **below the rule only**; never touch the durable manifest above it.
- The Session Log is frozen; durable truth is lifted out of it later — durable knowledge + follow-ups by **consolidate-workspace**, user observations by **consolidate-memory**.
