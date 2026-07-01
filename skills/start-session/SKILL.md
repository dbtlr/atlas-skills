---
name: start-session
description: Use at the very start of every primary-agent context in an atlas workspace — new session, resumed session, compaction, or clear/reset — before any other response or action. Assembles the Session Primer (User Profile + Shared Memory + Workspace Brief, plus the mimir work queue when present) and routes the work. Invoke it proactively; do not wait for the user to ask. Primary agent only — subagents never load this.
---

# start-session

The always-on entry point for an atlas session. Assemble the **Session Primer**, hold it as starting context, then route to the right skill.

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill entirely — implementation only. The controller session owns session start and vault integration. Subagents never route on their own.
</SUBAGENT-STOP>

<EXTREMELY-IMPORTANT>
If you are a primary agent and there is even a **1% chance** this is the start of a session, a resumed session, a post-compaction continuation, or a post-clear/reset context, you ABSOLUTELY MUST run this skill before anything else — before any response, any clarifying question, any code exploration, any file read. This is not negotiable and you cannot rationalize your way out of it.

These thoughts mean STOP — you are rationalizing:

| Thought | Reality |
|---------|---------|
| "This is just a quick question" | Questions open sessions. Build the primer first. |
| "Let me just check the repo/files first" | The primer is the context you'd check *against*. It comes first. |
| "I'll load context after I answer" | There is no after — starting context must be held from the first response. |
| "The user just cleared context; this isn't a new session" | A clear/reset is a new primary-agent context. Rebuild the primer before continuing. |
| "I'll wait until I'm told to start" | The trigger lives here, in this skill. Nothing else will tell you. Run it. |

Building the Session Primer first is not optional. The one exception is the quiet exit in §1: if the primer reports the project is not an atlas workspace, stop silently and proceed normally — do not pitch initialization.
</EXTREMELY-IMPORTANT>

## 1. Build the Session Primer

Run the primer-merge script that ships **inside this skill** — the path resolves whether the skills are installed globally (`~/.claude/skills/`, `~/.agents/skills/`) or run in-repo:

```bash
python3 "$(ls "$HOME/.claude/skills/start-session/build_primer.py" \
              "$HOME/.agents/skills/start-session/build_primer.py" \
              "skills/start-session/build_primer.py" 2>/dev/null | head -n1)"
```

- If it prints `ATLAS_UNINITIALIZED: …`, this project has no Project Binding (`.atlas.toml`) — it isn't an atlas workspace. **Stop silently and proceed with the user's request normally; do not mention atlas or pitch initialization.** This skill triggers on *any* session (the trigger lives in the skill, not in a per-project file), so an unbound project is the common, expected case — exit quietly. Only route to **initialize-atlas** if the user is explicitly setting up atlas (e.g. "initialize my workspace", "bind this repo to a vault").
- If it reports `ATLAS_PATH is not set`, the vault location is unknown — ask the user to `export ATLAS_PATH=<their atlas vault root>` (it always points at the atlas vault), then re-run.
- Otherwise, treat the printed payload as your **Active Context** for the session — User Profile, Shared Memory, the Workspace Brief, and (when the repo tracks work in Mimir) the current work queue. Internalize it; don't echo it back to the user.

## 2. Hold the through-line

A **Session** is bounded by a body of work, not by one context window. The primer is what you re-load on each resumption — including compactions, clears/resets, and new windows — to keep the work's through-line intact.

## 3. Decisions & glossary are live

The workspace `glossary.md` and `decisions/` are authored by the **`domain-modeling`** skill: it maintains the glossary (from the project's context/domain terms) and writes the ADRs. **Redirect that skill to the workspace location** — the vault workspace (`<ATLAS_PATH>/Workspaces/<workspace>/`), where `glossary.md` and `decisions/` live — rather than its default in-repo path.

**Repo override:** a repo may set `decisions = "local"` (or a path) in `.atlas.toml` to keep decisions/glossary *in the repo* instead of the vault workspace. When that key is present, honor the local target; otherwise default to the vault workspace.

Wherever they live, `glossary.md` and `decisions/` are **constraints on the work, not an archive** — hold them open the whole session, whatever you're doing (planning, brainstorming, building):

- **When planning, check the plan against `decisions/`.** A conflict means either the plan is wrong or the decision is stale — resolve it before building; never silently violate a recorded norm. Updating a decision can cascade, so do it thoughtfully.
- **Keep language true to `glossary.md`.** Use its canonical terms and let them frame the problem; challenge drift the moment you notice it.
- **Capture as it crystallizes** — a term sharpens → glossary; a hard-to-reverse, surprising, real-trade-off decision → an ADR (offer ADRs *sparingly*). Route both through `domain-modeling`.

This is general practice, not gated behind any one skill.

## 4. Routing surface

From the Active Context and what the user wants, route to:
- **initialize-atlas** — bind/scaffold/heal the workspace (also when the primer reports uninitialized).
- **write-session-log** — at a work boundary, memorialize the Session.
- **consolidate-sessions** — lift Consolidation Candidates from Session Logs into maintained context.

## 5. Keep the vault high-signal

Follow `resources/workspace-hygiene.md`: keep the Brief small, put new files in the right place, prune stale content, and trigger `write-session-log` at the right time. Don't bloat Active Context. When writing any file into the vault, follow the frontmatter rules in `resources/frontmatter.md` so agents can find and progressively disclose it.
