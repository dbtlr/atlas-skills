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
import re
import sys

# a PR URL in the command output — any GitHub host (github.com or Enterprise):
#   https://<host>/<owner>/<repo>/pull/<N>
PR_URL = re.compile(r"https://[^\s/]+/[^\s/]+/[^\s/]+/pull/(\d+)")

# Loose, non-tokenizing signal that a command CREATES a PR: `gh … pr … create`
# or `gh … api …/pulls`. It never tokenizes, so an unbalanced quote in a heredoc
# PR body can't defeat it — the exact failure that silently disabled the old
# shlex-based detector (ATSK-47). Precision comes from pairing it with a /pull/N
# URL in the command *output* (see main). That pair is a strong heuristic, not a
# proof: a URL in output confirms a PR *exists*, not that this command made it,
# so a non-create that both mentions "create" and prints a pull URL (a `gh pr
# comment --body "…create…"`, a `gh api …/pulls` read) can still nudge. That
# residual false-positive is accepted — a cheap advisory nudge on a PR that
# exists (usually one already being watched) — because the only way to be
# precise is to tokenize, the fragility we removed. Optimize against the
# expensive error (missing a real create), not the cheap one.
_GH_PR_CREATE = re.compile(r"\bgh\b.*?\bpr\b.*?\bcreate\b", re.S)
_GH_API_PULLS = re.compile(r"\bgh\b.*?\bapi\b.*?/pulls\b", re.S)


def creates_pr(command):
    """True if the command looks like it creates a PR — see the regex note above.
    Loose by design: precision comes from the output-URL gate in main(), not here."""
    return bool(_GH_PR_CREATE.search(command) or _GH_API_PULLS.search(command))


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
