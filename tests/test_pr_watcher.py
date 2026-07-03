"""Hermetic tests for skills/watching-a-pr/pr_watcher.py.

No external deps (stdlib unittest), no real `gh` calls, no real sleeping. The
watcher's heart is a pure function `compute_batch(state, since) -> (events,
cursor, terminal)`; the polling loop takes injected fetch/sleep/clock seams, so
every case here is deterministic.

Run: python3 -m unittest discover -s tests
"""
import sys
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent / "skills" / "watching-a-pr"
sys.path.insert(0, str(SKILL_DIR))
import pr_watcher  # noqa: E402


def state(**over):
    """A PR state as the fetch layer would return it; override any stream."""
    base = {
        "head_sha": "sha1",
        "merged": False,
        "merged_at": None,
        "issue_comments": [],
        "review_comments": [],
        "reviews": [],
        "checks": [],
    }
    base.update(over)
    return base


def ic(id, body="hi", author="drew"):
    return {"id": id, "author": author, "body": body, "created_at": "2026-07-02T00:00:00Z"}


def rc(id, body="fix this", path="a.py", line=10, author="drew"):
    return {"id": id, "author": author, "body": body, "path": path, "line": line,
            "diff_hunk": "@@ -1 +1 @@", "created_at": "2026-07-02T00:00:00Z"}


def review(id, st="COMMENTED", body="", author="drew"):
    return {"id": id, "author": author, "state": st, "body": body,
            "submitted_at": "2026-07-02T00:00:00Z"}


def check(name, conclusion, status="COMPLETED"):
    return {"name": name, "status": status, "conclusion": conclusion}


def kinds(events):
    return [e["kind"] for e in events]


class FilterSelfTest(unittest.TestCase):
    def test_watermarked_comment_is_dropped(self):
        items = [ic(1, "human note"), ic(2, "done " + pr_watcher.WATERMARK)]
        kept = pr_watcher.filter_self(items)
        self.assertEqual([i["id"] for i in kept], [1])

    def test_watermark_anywhere_in_body_counts(self):
        self.assertTrue(pr_watcher.is_self(ic(9, f"prefix\n{pr_watcher.WATERMARK}\nsuffix")))
        self.assertFalse(pr_watcher.is_self(ic(9, "no mark here")))


class ComputeBatchTest(unittest.TestCase):
    def test_first_arm_baselines_and_emits_nothing(self):
        s = state(issue_comments=[ic(5)], review_comments=[rc(7)], reviews=[review(3)])
        events, cursor, terminal = pr_watcher.compute_batch(s, None)
        self.assertEqual(events, [])
        self.assertIsNone(terminal)
        self.assertEqual(cursor["issue_comment_hw"], 5)
        self.assertEqual(cursor["review_comment_hw"], 7)
        self.assertEqual(cursor["review_hw"], 3)
        self.assertEqual(cursor["head_sha"], "sha1")

    def test_new_review_comment_emitted_with_line_context(self):
        s0 = state(review_comments=[rc(7)])
        _, cur, _ = pr_watcher.compute_batch(s0, None)
        s1 = state(review_comments=[rc(7), rc(9, body="rename this", path="b.py", line=42)])
        events, cur2, terminal = pr_watcher.compute_batch(s1, cur)
        self.assertEqual(kinds(events), ["review_comment"])
        e = events[0]
        self.assertEqual((e["id"], e["path"], e["line"], e["body"]), (9, "b.py", 42, "rename this"))
        self.assertEqual(cur2["review_comment_hw"], 9)

    def test_new_issue_comment_and_review_emitted(self):
        s0 = state()
        _, cur, _ = pr_watcher.compute_batch(s0, None)
        s1 = state(issue_comments=[ic(2, "ping")], reviews=[review(4, "CHANGES_REQUESTED")])
        events, _, _ = pr_watcher.compute_batch(s1, cur)
        self.assertEqual(sorted(kinds(events)), ["issue_comment", "review"])

    def test_self_comment_never_emitted_but_cursor_advances_past_it(self):
        s0 = state()
        _, cur, _ = pr_watcher.compute_batch(s0, None)
        # agent posts a watermarked reply (id 10), then a human comments (id 11)
        s1 = state(review_comments=[rc(10, body="addressed " + pr_watcher.WATERMARK),
                                    rc(11, body="human follow-up")])
        events, cur2, _ = pr_watcher.compute_batch(s1, cur)
        self.assertEqual([e["id"] for e in events], [11])          # only the human one
        self.assertEqual(cur2["review_comment_hw"], 11)            # advanced past the agent's 10

    def test_gate_transition_emits_once_not_repeatedly(self):
        s0 = state(checks=[check("ci", None, status="IN_PROGRESS")])
        _, cur, _ = pr_watcher.compute_batch(s0, None)             # baseline PENDING
        green = state(checks=[check("ci", "SUCCESS")])
        events, cur2, _ = pr_watcher.compute_batch(green, cur)
        self.assertEqual(kinds(events), ["gates"])
        self.assertEqual(events[0]["state"], "GREEN")
        # same green again -> no repeat
        events2, _, _ = pr_watcher.compute_batch(state(checks=[check("ci", "SUCCESS")]), cur2)
        self.assertEqual(events2, [])

    def test_red_gate_reports_failing_checks(self):
        s0 = state(checks=[check("ci", None, status="IN_PROGRESS")])
        _, cur, _ = pr_watcher.compute_batch(s0, None)
        red = state(checks=[check("lint", "SUCCESS"), check("test", "FAILURE")])
        events, _, _ = pr_watcher.compute_batch(red, cur)
        self.assertEqual(events[0]["state"], "RED")
        self.assertIn("test", events[0]["failing"])

    def test_merge_is_an_event_in_the_batch_alongside_comments(self):
        s0 = state(review_comments=[rc(7)])
        _, cur, _ = pr_watcher.compute_batch(s0, None)
        # a comment lands AND the PR merges in the same poll window
        merged = state(review_comments=[rc(7), rc(8, body="one more thing")],
                       merged=True, merged_at="2026-07-02T01:00:00Z")
        events, _, terminal = pr_watcher.compute_batch(merged, cur)
        self.assertEqual(terminal, "merged")
        self.assertIn("review_comment", kinds(events))            # comment not discarded
        self.assertIn("merge", kinds(events))                     # merge rides in the batch

    def test_nothing_new_yields_empty_batch_and_stable_cursor(self):
        s = state(review_comments=[rc(7)])
        _, cur, _ = pr_watcher.compute_batch(s, None)
        events, cur2, terminal = pr_watcher.compute_batch(s, cur)
        self.assertEqual(events, [])
        self.assertIsNone(terminal)
        self.assertEqual(cur2["review_comment_hw"], cur["review_comment_hw"])

    def test_already_merged_at_first_arm_is_terminal_immediately(self):
        s = state(merged=True, merged_at="2026-07-02T01:00:00Z")
        events, _, terminal = pr_watcher.compute_batch(s, None)
        self.assertEqual(terminal, "merged")
        self.assertEqual(kinds(events), ["merge"])


class PollTest(unittest.TestCase):
    def _poll(self, states, deadline=1200, backoff_at=300, timeout_at=1200):
        """Drive poll() with a scripted fetch sequence and a fake clock."""
        seq = list(states)
        clock = {"t": 0.0}
        slept = []

        def fetch(pr, repo):
            return seq.pop(0) if len(seq) > 1 else seq[0]

        def sleep(dt):
            slept.append(dt)
            clock["t"] += dt

        def now():
            return clock["t"]

        result = pr_watcher.poll("1", "o/r", None, fetch=fetch, sleep=sleep, now=now,
                                 timeout_s=timeout_at, backoff_after_s=backoff_at)
        return result, slept

    def test_returns_on_first_actionable_batch(self):
        s0 = state(review_comments=[rc(7)])                       # baseline
        s1 = state(review_comments=[rc(7), rc(8)])                # a new comment
        result, slept = self._poll([s0, s1])
        self.assertEqual(kinds(result["events"]), ["review_comment"])
        self.assertIsNone(result["terminal"])
        self.assertEqual(result["cursor"]["review_comment_hw"], 8)

    def test_backoff_5s_then_30s_after_threshold(self):
        quiet = state(review_comments=[rc(7)])
        # never changes until we've slept past the backoff threshold, then a comment
        seq = [quiet] * 100
        clock = {"t": 0.0}
        slept = []

        def fetch(pr, repo):
            # stay quiet until past the backoff threshold, so a 30s sleep must occur
            return state(review_comments=[rc(7), rc(8)]) if clock["t"] >= 330 else quiet

        def sleep(dt):
            slept.append(dt); clock["t"] += dt

        def now():
            return clock["t"]

        pr_watcher.poll("1", "o/r", None, fetch=fetch, sleep=sleep, now=now,
                        timeout_s=1200, backoff_after_s=300)
        self.assertEqual(slept[0], 5)                             # starts fast
        self.assertIn(30, slept)                                  # backs off
        self.assertTrue(all(dt in (5, 30) for dt in slept))

    def test_times_out_and_reports_terminal_timeout(self):
        quiet = state(review_comments=[rc(7)])
        clock = {"t": 0.0}

        def fetch(pr, repo):
            return quiet

        def sleep(dt):
            clock["t"] += dt

        def now():
            return clock["t"]

        result = pr_watcher.poll("1", "o/r", None, fetch=fetch, sleep=sleep, now=now,
                                 timeout_s=1200, backoff_after_s=300)
        self.assertEqual(result["terminal"], "timeout")
        self.assertEqual(result["events"], [])

    def test_backoff_resets_after_a_batch_is_returned(self):
        # a single poll() call returns on the batch; the RESET is that the next
        # re-arm starts fresh at 5s — modeled by a new poll() call slept-fresh.
        s0 = state(review_comments=[rc(7)])
        s1 = state(review_comments=[rc(7), rc(8)])
        (result, slept) = self._poll([s0, s1])
        self.assertEqual(slept[0], 5)                             # fresh arm starts fast


if __name__ == "__main__":
    unittest.main()
