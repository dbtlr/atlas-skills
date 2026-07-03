#!/usr/bin/env python3
"""pr-watcher — watch an open GitHub PR in the background and exit with a batch.

The externally-stateless engine behind the `watching-a-pr` skill. Its heart is a
pure function, `compute_batch(state, since) -> (events, cursor, terminal)`: given
the PR's current state and the high-water cursor the agent handed back, it returns
everything of interest since that cursor, the advanced cursor, and whether the PR
reached a terminal (merged/timeout). No state is kept on disk — continuity lives in
the cursor, which the agent owns and passes back on each re-arm — so the logic is a
deterministic function of (state, since) and is unit-testable by mocking `gh`.

The `poll()` loop wraps the pure core with a backoff schedule and injected
fetch/sleep/clock seams. Only `main()` touches the real `gh` and the real clock.

Contract (stdout, exit 0 on a normal result; nonzero only on an operational failure
of the watcher itself, e.g. `gh` broke):

    { "events": [ {kind, ...}, ... ], "cursor": {...}, "terminal": "merged"|"timeout"|null }

The agent processes the whole batch, then the terminal flag decides re-arm vs stop —
a merge is an event *in* the batch, never a short-circuit that discards the comments
that rode in with it.
"""
import argparse
import json
import subprocess
import sys
import time

# Agent-authored PR comments carry this marker so the watcher skips its own replies —
# necessary because the agent posts under the same GitHub identity as the human, so
# filtering by author can't tell them apart.
WATERMARK = "<!-- claude-watcher:seen -->"

# Contract: the agent marks its own PR artifacts with WATERMARK so the watcher skips
# them (author-filtering can't, since agent and human share the GitHub identity). This
# requires agent-posted artifacts to *carry a body* — the `watching-a-pr` skill posts
# watermarked comments, not empty-bodied formal reviews, so an empty agent review can't
# self-feed. Enforced by the poster (piece 5), not detectable here.
_RED_CONCLUSIONS = {"FAILURE", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED",
                    "STARTUP_FAILURE", "STALE"}
_GREEN_CONCLUSIONS = {"SUCCESS", "NEUTRAL", "SKIPPED"}


def is_self(item):
    """True if a comment/review was authored by the agent (carries the watermark).

    Matches the watermark only on its own *unquoted* line, so a human "Quote reply"
    that pulls the marker into a `> `-prefixed quote is not mistaken for the agent."""
    return any(line.strip() == WATERMARK for line in (item.get("body") or "").splitlines())


def filter_self(items):
    return [it for it in items if not is_self(it)]


def gate_state(checks):
    """Aggregate the check rollup into PENDING / GREEN / RED.

    Only *settles* (GREEN/RED) once every check is COMPLETED; a still-running check
    keeps it PENDING. Once settled, an unrecognized conclusion counts as RED rather
    than hanging PENDING forever (e.g. GitHub's STALE, or a null conclusion)."""
    if not checks:
        return "PENDING"
    if not all((c.get("status") or "").upper() == "COMPLETED" for c in checks):
        return "PENDING"
    concl = [(c.get("conclusion") or "").upper() for c in checks]
    if any(c in _RED_CONCLUSIONS for c in concl):
        return "RED"
    if all(c in _GREEN_CONCLUSIONS for c in concl):
        return "GREEN"
    return "RED"  # all done but an unrecognized conclusion — surface it, never hang


def _failing(checks):
    return sorted(c["name"] for c in checks
                  if (c.get("conclusion") or "").upper() in _RED_CONCLUSIONS)


def gate_signature(checks):
    """A signature that changes whenever the *settled outcome set* changes — so a
    second check failing while already RED, or a different failing set, re-emits."""
    return gate_state(checks) + ":" + ",".join(_failing(checks))


def _stream(items, prev_hw, first_arm, make_event):
    """Advance the high-water over every item (self included, monotonic), but emit an
    event only for genuinely-new, non-self items."""
    events, hw = [], prev_hw
    for it in items:
        hw = max(hw, it["id"])
        if not first_arm and it["id"] > prev_hw and not is_self(it):
            events.append(make_event(it))
    return events, hw


def compute_batch(state, since):
    """Pure: (events, new_cursor, terminal) for the PR `state` given the `since` cursor.

    since=None (or empty) is the first arm — it baselines to the current high-waters
    and emits nothing (only what arrives afterward is new), except a merge, which is
    terminal whenever it is seen."""
    since = since or {}
    first_arm = not since

    ic_events, ic_hw = _stream(
        state.get("issue_comments", []), since.get("issue_comment_hw", 0), first_arm,
        lambda c: {"kind": "issue_comment", "id": c["id"], "author": c.get("author"),
                   "body": c.get("body"), "created_at": c.get("created_at")})
    rc_events, rc_hw = _stream(
        state.get("review_comments", []), since.get("review_comment_hw", 0), first_arm,
        lambda c: {"kind": "review_comment", "id": c["id"], "author": c.get("author"),
                   "path": c.get("path"), "line": c.get("line"), "body": c.get("body"),
                   "diff_hunk": c.get("diff_hunk"), "created_at": c.get("created_at")})
    rv_events, rv_hw = _stream(
        state.get("reviews", []), since.get("review_hw", 0), first_arm,
        lambda r: {"kind": "review", "id": r["id"], "author": r.get("author"),
                   "state": r.get("state"), "body": r.get("body"),
                   "submitted_at": r.get("submitted_at")})

    events = ic_events + rc_events + rv_events

    checks = state.get("checks", [])
    gs = gate_state(checks)
    sig = gate_signature(checks)
    # When the head advances (a pushed fix), the gate baseline resets — the new
    # commit's settled result must re-emit even if its color matches the old one,
    # otherwise an already-complete re-run is silently dropped.
    head_changed = (not first_arm and since.get("head_sha") is not None
                    and state.get("head_sha") != since.get("head_sha"))
    prev_sig = None if head_changed else since.get("gate_sig")
    if not first_arm and gs in ("GREEN", "RED") and sig != prev_sig:
        events.append({"kind": "gates", "state": gs, "failing": _failing(checks)})

    terminal = None
    if state.get("merged"):
        terminal = "merged"
        events.append({"kind": "merge", "merged_at": state.get("merged_at"),
                       "head_sha": state.get("head_sha")})

    cursor = {
        "issue_comment_hw": ic_hw,
        "review_comment_hw": rc_hw,
        "review_hw": rv_hw,
        "head_sha": state.get("head_sha"),
        "gate_sig": sig,
    }
    return events, cursor, terminal


def poll(pr, repo, since, *, fetch, sleep, now,
         timeout_s=1200, backoff_after_s=300, fast_s=5, slow_s=30):
    """Poll until an actionable batch or a terminal; return the result dict.

    Wakes the agent only when it returns — i.e. on a non-empty batch or a terminal.
    Backoff is fast until `backoff_after_s` of quiet, then slow; a fresh call (re-arm)
    starts fast again, which is how a cursor advance resets the backoff."""
    start = now()
    cursor = since
    while True:
        state = fetch(pr, repo)
        events, cursor, terminal = compute_batch(state, cursor)
        if events or terminal:
            return {"events": events, "cursor": cursor, "terminal": terminal}
        if now() - start >= timeout_s:
            return {"events": [], "cursor": cursor, "terminal": "timeout"}
        sleep(fast_s if (now() - start) < backoff_after_s else slow_s)


# ---- real gh layer (only main() reaches here) -------------------------------------

def _gh_json(args):
    out = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=30)
    if out.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed: {out.stderr.strip()}")
    return json.loads(out.stdout or "null")


def _gh_object_pages(path, key):
    """Paginate an *object*-returning endpoint and flatten `key` across pages.

    `gh api --paginate` concatenates one JSON object per page for object endpoints
    (e.g. check-runs), which json.loads can't parse; `--slurp` wraps the pages in an
    array so we can merge their inner lists."""
    pages = _gh_json(["api", path, "--paginate", "--slurp"]) or []
    items = []
    for pg in pages:
        items.extend((pg or {}).get(key, []) or [])
    return items


def fetch_state(pr, repo):
    """Assemble the PR state from `gh api`, mapped to the shape compute_batch wants."""
    pull = _gh_json(["api", f"repos/{repo}/pulls/{pr}"])
    head_sha = (pull.get("head") or {}).get("sha")
    review_comments = [
        {"id": c["id"], "author": (c.get("user") or {}).get("login"),
         "body": c.get("body"), "path": c.get("path"),
         "line": c.get("line") or c.get("original_line"),
         "diff_hunk": c.get("diff_hunk"), "created_at": c.get("created_at")}
        for c in _gh_json(["api", f"repos/{repo}/pulls/{pr}/comments", "--paginate"])]
    issue_comments = [
        {"id": c["id"], "author": (c.get("user") or {}).get("login"),
         "body": c.get("body"), "created_at": c.get("created_at")}
        for c in _gh_json(["api", f"repos/{repo}/issues/{pr}/comments", "--paginate"])]
    reviews = [
        {"id": r["id"], "author": (r.get("user") or {}).get("login"),
         "state": r.get("state"), "body": r.get("body"),
         "submitted_at": r.get("submitted_at")}
        for r in _gh_json(["api", f"repos/{repo}/pulls/{pr}/reviews", "--paginate"])]
    checks = []
    if head_sha:
        # Check Runs API (GitHub Actions et al.)…
        checks = [{"name": c.get("name"), "status": (c.get("status") or "").upper(),
                   "conclusion": (c.get("conclusion") or None)}
                  for c in _gh_object_pages(f"repos/{repo}/commits/{head_sha}/check-runs",
                                            "check_runs")]
        # …plus the legacy commit Status API (many external CI providers post here, not
        # as check-runs). Missing them would let the gate read GREEN on a pending/red
        # required status. Map its states into the same check shape.
        status = _gh_json(["api", f"repos/{repo}/commits/{head_sha}/status"]) or {}
        _st = {"success": ("COMPLETED", "SUCCESS"), "failure": ("COMPLETED", "FAILURE"),
               "error": ("COMPLETED", "FAILURE"), "pending": ("IN_PROGRESS", None)}
        for s in (status.get("statuses") or []):
            st, concl = _st.get(s.get("state"), ("IN_PROGRESS", None))
            checks.append({"name": s.get("context"), "status": st, "conclusion": concl})
    return {
        "head_sha": head_sha,
        "merged": bool(pull.get("merged")),
        "merged_at": pull.get("merged_at"),
        "issue_comments": issue_comments,
        "review_comments": review_comments,
        "reviews": reviews,
        "checks": checks,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Watch a GitHub PR; exit with a batch.")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--repo", help="owner/name (default: current repo)")
    ap.add_argument("--since", help="JSON cursor from a previous run (omit to arm fresh)")
    ap.add_argument("--timeout", type=int, default=1200)
    ap.add_argument("--backoff-after", type=int, default=300)
    args = ap.parse_args(argv)

    try:
        repo = args.repo or _gh_json(["repo", "view", "--json", "nameWithOwner"])["nameWithOwner"]
        since = json.loads(args.since) if args.since else None
        result = poll(args.pr, repo, since, fetch=fetch_state, sleep=time.sleep,
                      now=time.monotonic, timeout_s=args.timeout,
                      backoff_after_s=args.backoff_after)
    except Exception as exc:  # operational failure of the watcher itself
        json.dump({"error": str(exc)}, sys.stdout)
        sys.stdout.write("\n")
        return 1
    json.dump(result, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
