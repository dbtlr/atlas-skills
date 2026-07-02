#!/usr/bin/env python3
"""PreToolUse hook: block `gh pr create` unless the branch carries an Adversarial-Review trailer.

Reads the Claude Code hook payload from stdin. For Bash commands that create a PR,
greps the commits ahead of the integration branch for the disposition trailer the
adversarial-review skill writes (`Adversarial-Review: run …` or
`Adversarial-Review: skipped reason=…`). Absent trailer -> exit 2 (block, stderr fed
back to the model). Everything else -> exit 0 (allow).

Fail-open by design everywhere except the one state it exists to catch: a PR being
created off reviewable commits with no disposition on record. Stdlib only.
"""

import json
import re
import subprocess
import sys

PR_CREATE = re.compile(r"\bgh\s+pr\s+create\b")
TRAILER = re.compile(r"^Adversarial-Review: (run|skipped)\b", re.MULTILINE)


def sh(args, cwd):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


def resolve_base(cwd):
    """The integration branch, resolved the same way the skill resolves it."""
    r = sh(["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"], cwd)
    if r.returncode == 0:
        return r.stdout.strip()
    sh(["git", "remote", "set-head", "origin", "--auto"], cwd)
    r = sh(["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"], cwd)
    if r.returncode == 0:
        return r.stdout.strip()
    for ref in ("origin/main", "origin/master"):
        if sh(["git", "show-ref", "--verify", "--quiet", f"refs/remotes/{ref}"], cwd).returncode == 0:
            return ref
    return None


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not PR_CREATE.search(command):
        return 0

    cwd = payload.get("cwd") or "."
    if sh(["git", "rev-parse", "--git-dir"], cwd).returncode != 0:
        return 0  # not a repo — let gh produce its own error

    base = resolve_base(cwd)
    if base is None:
        return 0  # no resolvable integration branch — nothing to measure against

    log = sh(["git", "log", f"{base}..HEAD", "--format=%B"], cwd)
    if log.returncode != 0 or not log.stdout.strip():
        return 0  # detached/odd state, or no commits ahead — gh will complain itself

    if TRAILER.search(log.stdout):
        return 0

    sys.stderr.write(
        f"BLOCKED by the adversarial-review gate: no Adversarial-Review trailer on any "
        f"commit in {base}..HEAD. Before creating a PR, run the adversarial-review "
        f"skill: review the committed diff at the gate's tier (or declare a skip), "
        f"resolve every finding to a terminal state, and commit the disposition "
        f"trailer — `Adversarial-Review: run engine=… tier=… findings=… fixed=… "
        f"dismissed=… deferred=…` or `Adversarial-Review: skipped reason=…`. "
        f"Then retry the PR.\n"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
