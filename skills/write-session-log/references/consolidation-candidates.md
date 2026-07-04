# Consolidation Candidates

A **Consolidation Candidate** is an item a Session Log flags as worth lifting out of the frozen record during Consolidation. Three buckets, each routing to the tool that owns it.

## Carried candidates (recurrence)

A candidate is **carried** when it repeats one a prior Session Log already raised that was **never actioned** (still not filed, decided, or promoted). Mark a carried candidate `carried (since <YYYY-MM-DD>)` — first-raised date, optionally a count — instead of re-listing it as fresh. This makes recurrence legible in the candidate itself.

- **write-session-log** applies the mark (detection only — it never files or decides).
- **consolidate-workspace** acts on it: a candidate carried across **≥2 runs** is itself the signal to escalate — file it or force a decision, don't let it be carried again. (It also detects recurrence directly across the log window, so the mark is an aid, not a gate.)

## Taxonomy

### Durable knowledge
- `decision` — a decision that will affect future work
- `user-persona` — something newly learned about the target user
- `user-story` — a user story that surfaced and should be honored going forward

### Future opportunities
- `tech-debt` — debt incurred; remember it (promote to a task if high priority)
- `follow-up-task` — work that resulted from / was discovered during this session
- `open-question` — unresolved question to revisit

### User observations
- `collaboration-pattern` — something that helps future agents work better with the user

## Routing

Two skills own different buckets, keyed on different session-log flags — each scans (`norn -C "$ATLAS_PATH" find`) and marks (`norn -C "$ATLAS_PATH" set`) only its own flag:

| Bucket | Routes to | Skill (flag) |
|--------|-----------|--------------|
| Durable knowledge | Workspace Brief / `decisions/` / `notes/` | **consolidate-workspace** (`workspace_consolidated`) |
| Future opportunities | a Mimir task | **consolidate-workspace** (`workspace_consolidated`) |
| User observations | the shared profile (`user.md` / `memory.md`), cross-project | **consolidate-memory** (`memory_consolidated`) |

The Session Log is the only consolidation source. Once consolidated it is **spent** — frozen but prunable, not a permanent archive.
