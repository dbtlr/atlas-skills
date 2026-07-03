#!/usr/bin/env python3
"""PostToolUse hook: after a PR is created, nudge the agent to arm the watcher.

The `finishing-a-task` workflow hands a freshly-opened PR to `watching-a-pr`. This
hook is the **backstop** for a PR created *outside* that flow — an agent that just
runs `gh pr create` directly. It fires after a Bash `gh pr create` that succeeded,
extracts the PR number from the command's output, and injects a systemMessage telling
the agent to arm `watching-a-pr`.

It only *nudges* — a PostToolUse hook can't launch the durable background watcher
itself (a hook-spawned process isn't harness-tracked to re-invoke the agent); only a
watcher the agent launches has that wiring. So the hook's whole job is to make sure
the agent knows a PR now exists and should be watched.

Reads the Claude Code hook payload from stdin. Emits `{"systemMessage": ...}` when a
PR was created, nothing otherwise. Fail-open on every ambiguity. Stdlib only.
"""
import json
import re
import shlex
import sys

SHELL_SEPARATORS = {"&&", "||", "|", ";", "&", "(", ")", "{", "}", "\n"}
# a PR URL in the command output, e.g. https://github.com/owner/name/pull/123
PR_URL = re.compile(r"https://github\.com/[^/\s]+/[^/\s]+/pull/(\d+)")


def command_name(seg):
    i = 0
    while i < len(seg) and "=" in seg[i] and not seg[i].startswith("-") \
            and "/" not in seg[i].split("=", 1)[0]:
        i += 1
    if i >= len(seg):
        return None, []
    return seg[i].rsplit("/", 1)[-1], seg[i + 1:]


def creates_pr(command):
    """True if any segment of the command is a `gh … pr … create` (flags may interleave)."""
    try:
        tokens = shlex.split(command, comments=False)
    except ValueError:
        return False
    seg = []
    segs = []
    for tok in tokens:
        if tok in SHELL_SEPARATORS:
            if seg:
                segs.append(seg)
                seg = []
        else:
            seg.append(tok)
    if seg:
        segs.append(seg)
    for s in segs:
        name, args = command_name(s)
        if name == "gh" and "pr" in args and "create" in args and "--help" not in args:
            return True
    return False


def _result_text(payload):
    """The tool's output text, across the shapes PostToolUse payloads use."""
    r = payload.get("tool_result")
    if isinstance(r, str):
        return r
    if isinstance(r, dict):
        return " ".join(str(v) for v in (r.get("stdout"), r.get("output"),
                                         r.get("stderr")) if v)
    return payload.get("tool_response") or ""


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not creates_pr(command):
        return 0

    m = PR_URL.search(_result_text(payload))
    if not m:
        return 0  # no PR URL in the output — creation likely failed; nothing to watch
    pr = m.group(1)

    json.dump({"systemMessage":
               f"PR #{pr} was created. If you are not already watching it, invoke the "
               f"`watching-a-pr` skill with PR #{pr} to carry it through CI, review "
               f"comments, and merge."}, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
