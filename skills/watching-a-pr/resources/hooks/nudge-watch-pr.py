#!/usr/bin/env python3
"""PostToolUse hook: after a PR is created, nudge the agent to arm the watcher.

The `finishing-a-task` workflow hands a freshly-opened PR to `watching-a-pr`. This
hook is the **backstop** for a PR created *outside* that flow — an agent that just
runs `gh pr create` directly. It fires after a Bash command that creates a PR,
extracts the PR number from the command's output, and injects a systemMessage telling
the agent to arm `watching-a-pr`.

It only *nudges* — a PostToolUse hook can't launch the durable background watcher
itself (a hook-spawned process isn't harness-tracked to re-invoke the agent); only a
watcher the agent launches has that wiring. So the hook's whole job is to make sure
the agent knows a PR now exists and should be watched.

Reads the Claude Code hook payload from stdin. The Bash output is in `tool_output`
(a string). Emits `{"systemMessage": ...}` when a PR URL is present in that output,
nothing otherwise. **Fail-open, unconditionally** — the whole body is guarded so no
payload shape can make the hook crash the tool call. Stdlib only.
"""
import json
import shlex
import sys

SHELL_SEPARATORS = {"&&", "||", "|", ";", "&", "(", ")", "{", "}", "\n"}
# a PR URL in the command output — any GitHub host (github.com or Enterprise):
#   https://<host>/<owner>/<repo>/pull/<N>
import re
PR_URL = re.compile(r"https://[^\s/]+/[^\s/]+/[^\s/]+/pull/(\d+)")


def _segments(command):
    """Operator-separated segments of shell tokens; quoting respected."""
    try:
        tokens = shlex.split(command, comments=False)
    except ValueError:
        return []
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
    """Invoked binary's basename, skipping leading `VAR=val` env assignments."""
    i = 0
    while i < len(seg) and "=" in seg[i] and not seg[i].startswith("-") \
            and "/" not in seg[i].split("=", 1)[0]:
        i += 1
    if i >= len(seg):
        return None, []
    return seg[i].rsplit("/", 1)[-1], seg[i + 1:]


def creates_pr(command):
    """True if any segment creates a PR: `gh … pr … create` or `gh api …/pulls`.

    Kept in parity with check-adversarial-review.py's detection (the two hooks share
    this shell-parsing shape by convention, not a cross-skill import)."""
    for seg in _segments(command):
        name, args = command_name(seg)
        if name != "gh" or "--help" in args or "-h" in args:
            continue
        if "pr" in args and "create" in args:
            return True
        if "api" in args and any("/pulls" in a for a in args):
            return True
    return False


def output_text(payload):
    """The Bash tool's output text. `tool_output` is a string; defend against any
    other shape so the hook can never crash on an unexpected payload."""
    out = payload.get("tool_output")
    if isinstance(out, str):
        return out
    if isinstance(out, dict):
        return " ".join(str(v) for v in out.values() if isinstance(v, str))
    return "" if out is None else str(out)


def main():
    try:
        payload = json.load(sys.stdin)
        if payload.get("tool_name") != "Bash":
            return 0
        command = (payload.get("tool_input") or {}).get("command") or ""
        if not creates_pr(command):
            return 0
        # gh prints the created PR's URL last on stdout; take the last match so a URL
        # referenced in the command body (echoed earlier) can't win.
        matches = PR_URL.findall(output_text(payload))
        if not matches:
            return 0  # no PR URL — creation produced none (failed); nothing to watch
        pr = matches[-1]
        json.dump({"systemMessage":
                   f"PR #{pr} is open. If you are not already watching it, invoke the "
                   f"`watching-a-pr` skill with PR #{pr} to carry it through CI, review "
                   f"comments, and merge."}, sys.stdout)
        sys.stdout.write("\n")
    except Exception:
        return 0  # fail-open: a hook must never crash the tool call
    return 0


if __name__ == "__main__":
    sys.exit(main())
