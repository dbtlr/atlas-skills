#!/usr/bin/env python3
"""PreToolUse hook: nudge `gh pr create` toward carrying an Adversarial-Review trailer.

Reads the Claude Code hook payload from stdin. For a Bash command that creates a PR,
greps the commits ahead of the PR's base branch for the disposition trailer the
adversarial-review skill writes (`Adversarial-Review: run …` / `skipped …`). Absent
trailer -> exit 2 (block, stderr fed back to the model). Everything else -> exit 0.

This is a **speed bump for the forgotten gate, not a security boundary.** It catches
the ordinary case — an agent about to `gh pr create` without having run the review —
by parsing the command into shell segments and matching `gh` invocations by their
subcommand tokens (so a commit message that merely mentions the phrase is not a PR,
and flags interleaved among `pr … create` still match). It does NOT stop an agent
determined to evade it (a `gh` alias, `gh api …/pulls`, or another tool can create a
PR through a path this can't see). That's acceptable: the skill fights rationalized
skipping, and a human still sees every PR. Stdlib only; fail-open on every ambiguity.
"""

import json
import shlex
import subprocess
import sys

SHELL_SEPARATORS = {"&&", "||", "|", ";", "&", "(", ")", "{", "}", "\n"}
TRAILER = "Adversarial-Review:"


def sh(args, cwd):
    """Run git; any OSError (e.g. cwd deleted) or failure resolves to a fail-open None."""
    try:
        return subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=8)
    except (OSError, subprocess.SubprocessError):
        return None


def segments(command):
    """Split a shell command into operator-separated segments of tokens.

    Quoting is respected, so `gh pr create` inside a `-m "…"` argument stays one
    token and never reads as a PR-creating segment. Unparseable -> None (fail open)."""
    try:
        tokens = shlex.split(command, comments=False)
    except ValueError:
        return None
    segs, cur = [], []
    for tok in tokens:
        if tok in SHELL_SEPARATORS:
            if cur:
                segs.append(cur)
                cur = []
        else:
            cur.append(tok)
    if cur:
        segs.append(cur)
    return segs


def command_name(seg):
    """The invoked binary's basename, skipping leading `VAR=val` env assignments."""
    i = 0
    while i < len(seg) and "=" in seg[i] and not seg[i].startswith("-") \
            and "/" not in seg[i].split("=", 1)[0]:
        i += 1
    if i >= len(seg):
        return None, []
    return seg[i].rsplit("/", 1)[-1], seg[i + 1:]


def pr_base(seg):
    """If a segment creates a PR, return (True, base_branch_or_None); else (False, None).

    Matches `gh … pr … create …` (flags may interleave) and `gh api …/pulls …`.
    `--help`/`-h` is not a creation. Honors `--base`/`-B`/`-B=`."""
    name, args = command_name(seg)
    if name != "gh":
        return False, None
    if "--help" in args or "-h" in args:
        return False, None

    is_create = "pr" in args and "create" in args
    is_api = "api" in args and any("/pulls" in a for a in args)
    if not (is_create or is_api):
        return False, None

    base = None
    for i, a in enumerate(args):
        if a in ("--base", "-B") and i + 1 < len(args):
            base = args[i + 1]
        elif a.startswith("--base="):
            base = a.split("=", 1)[1]
        elif a.startswith("-B="):
            base = a.split("=", 1)[1]
    return True, base


def resolve_base(cwd, requested):
    """Resolve the base branch to a local ref — no network. None -> fail open.

    Honors an explicit `--base`; otherwise origin/HEAD, then origin/main|master."""
    def have(ref):
        r = sh(["git", "show-ref", "--verify", "--quiet", f"refs/remotes/{ref}"], cwd)
        return r is not None and r.returncode == 0

    if requested:
        req = requested if requested.startswith("origin/") else f"origin/{requested}"
        if have(req):
            return req
        # local branch fallback for a base that isn't a remote-tracking ref
        r = sh(["git", "rev-parse", "--verify", "--quiet", requested], cwd)
        return requested if (r is not None and r.returncode == 0 and r.stdout.strip()) else None

    r = sh(["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"], cwd)
    if r is not None and r.returncode == 0 and r.stdout.strip():
        return r.stdout.strip()
    for ref in ("origin/main", "origin/master"):
        if have(ref):
            return ref
    return None


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""

    segs = segments(command)
    if segs is None:
        return 0
    base_req, creates = None, False
    for seg in segs:
        hit, b = pr_base(seg)
        if hit:
            creates = True
            base_req = base_req or b
    if not creates:
        return 0

    cwd = payload.get("cwd") or "."
    if sh(["git", "rev-parse", "--git-dir"], cwd) is None:
        return 0  # cwd gone or not a repo — let gh surface its own error
    if sh(["git", "rev-parse", "--git-dir"], cwd).returncode != 0:
        return 0

    base = resolve_base(cwd, base_req)
    if base is None:
        return 0  # no resolvable base — nothing to measure against

    log = sh(["git", "log", f"{base}..HEAD", "--format=%B"], cwd)
    if log is None or log.returncode != 0 or not log.stdout.strip():
        return 0  # detached/odd state or no commits ahead — gh will complain itself
    if TRAILER in log.stdout:
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
