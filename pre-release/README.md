# pre-release

Skills parked outside the install path. The `skills` CLI discovers `SKILL.md`
files recursively under `skills/` — including nested subdirectories — so a
disabled skill must live outside that tree entirely to stay out of
`npx skills add --all`. This directory is that holding area.

Skills here are kept intact and tested where applicable, but are **not
installed** and **not part of the released set**. To release (or re-release)
one, move its directory back under `skills/` and update the skill lists in
`README.md` and `AGENTS.md`.

Currently parked:

- `adversarial-review` — the pre-PR verification gate (proportionality gate,
  suppression scan, delegated review, resolution loop, disposition trailer).
  Parked as too prescriptive for everyday flow; its enforcement hook and tests
  remain functional.
- `finishing-a-task` — the "done → merged" orchestrator built around a
  mandatory `adversarial-review` step. Parked together with it; `watching-a-pr`
  remains released and can be invoked directly with a PR number.
