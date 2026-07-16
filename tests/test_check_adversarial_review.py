"""Hermetic tests for pre-release/adversarial-review/resources/hooks/check-adversarial-review.py.

The pre-PR adversarial-review gate. Each test builds a throwaway git repo (a base
commit reachable as origin/main, one feature commit ahead) under a temp dir, feeds
the hook a PreToolUse payload on stdin, and asserts the exit code: 0 = allow, 2 =
block. No network, no `gh`. Run: python3 -m unittest discover -s tests
"""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOK = (Path(__file__).resolve().parent.parent / "pre-release" / "adversarial-review"
        / "resources" / "hooks" / "check-adversarial-review.py")
_spec = importlib.util.spec_from_file_location("check_adversarial_review", HOOK)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

TRAILER = ("Adversarial-Review: run engine=code-review tier=high "
           "findings=0 fixed=0 dismissed=0 deferred=0")

# A real multi-line PR body written via a heredoc whose text carries apostrophes
# (odd single-quote count) — the exact shape that made shlex.split raise, so the
# old gate returned None and fail-opened, letting an unreviewed PR through.
HEREDOC_CREATE = (
    "cat > /tmp/body.md <<'EOF'\n"
    "## Summary\nderived from the section's tail; block()'s and node's\nEOF\n"
    "gh pr create --title x --body-file /tmp/body.md")


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def make_repo(tmp, feature_msg):
    """Repo with origin/main as base and one feature commit carrying feature_msg."""
    r = Path(tmp)
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "t@t.t")
    _git(r, "config", "user.name", "t")
    (r / "a.txt").write_text("base\n")
    _git(r, "add", "a.txt")
    _git(r, "commit", "-qm", "base")
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=r,
                          capture_output=True, text=True).stdout.strip()
    _git(r, "update-ref", "refs/remotes/origin/main", base)
    _git(r, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
    _git(r, "checkout", "-qb", "feature")
    (r / "b.txt").write_text("work\n")
    _git(r, "add", "b.txt")
    _git(r, "commit", "-qm", feature_msg)
    return str(r)


def run(command, cwd="."):
    p = subprocess.run([sys.executable, str(HOOK)], capture_output=True, text=True,
                       input=json.dumps({"tool_name": "Bash",
                                         "tool_input": {"command": command}, "cwd": cwd}))
    return p.returncode, p.stderr


class GateEndToEnd(unittest.TestCase):
    def test_blocks_plain_create_without_trailer(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, err = run("gh pr create", make_repo(tmp, "feat: x"))
            self.assertEqual(code, 2)
            self.assertIn("BLOCKED", err)

    def test_allows_plain_create_with_trailer(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _ = run("gh pr create", make_repo(tmp, "feat: x\n\n" + TRAILER))
            self.assertEqual(code, 0)

    def test_blocks_heredoc_create_without_trailer(self):
        # Regression (ATSK-39): the heredoc-apostrophe command defeated shlex, so
        # the old gate fail-opened. Heredoc-strip lets it parse and be gated.
        with tempfile.TemporaryDirectory() as tmp:
            code, err = run(HEREDOC_CREATE, make_repo(tmp, "feat: x"))
            self.assertEqual(code, 2)
            self.assertIn("BLOCKED", err)

    def test_allows_heredoc_create_with_trailer(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _ = run(HEREDOC_CREATE, make_repo(tmp, "feat: x\n\n" + TRAILER))
            self.assertEqual(code, 0)

    def test_ignores_non_pr_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(run("git status", make_repo(tmp, "feat: x"))[0], 0)

    def test_blocks_create_after_heredoc_lookalike_in_earlier_line(self):
        # Bypass regression: a `<<WORD` inside a quoted string on an earlier line is
        # not a real heredoc (no terminator). strip_heredocs must NOT swallow the
        # following real `gh pr create`, or it slips past the gate parseable-but-
        # gh-stripped, never reaching the fail-closed backstop.
        cmd = 'git commit -m "document the <<HEREDOC pattern"\ngh pr create --title x'
        with tempfile.TemporaryDirectory() as tmp:
            code, err = run(cmd, make_repo(tmp, "feat: x"))
            self.assertEqual(code, 2)
            self.assertIn("BLOCKED", err)

    def test_blocks_newline_separated_create(self):
        # the newline->';' segmentation: a create on its own line after another
        # command must not hide behind the first line's binary.
        with tempfile.TemporaryDirectory() as tmp:
            code, _ = run("cd sub\ngh pr create --title x", make_repo(tmp, "feat: x"))
            self.assertEqual(code, 2)

    def test_blocks_indented_heredoc_create_without_trailer(self):
        cmd = ("cat > /tmp/b.md <<-EOF\n\t## Body with section's tail\n\tEOF\n"
               "gh pr create --title x --body-file /tmp/b.md")
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(run(cmd, make_repo(tmp, "feat: x"))[0], 2)

    def test_blocks_create_after_two_sequential_heredocs(self):
        cmd = ("cat > a <<'A'\nbody a's text\nA\n"
               "cat > b <<'B'\nbody b's text\nB\n"
               "gh pr create --title x")
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(run(cmd, make_repo(tmp, "feat: x"))[0], 2)

    def test_blocks_api_pulls_create_without_trailer(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _ = run("gh api repos/o/r/pulls -f title=x -f head=h -f base=main",
                          make_repo(tmp, "feat: x"))
            self.assertEqual(code, 2)

    def test_non_bash_tool_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = {"tool_name": "Read", "tool_input": {"command": "gh pr create"},
                       "cwd": make_repo(tmp, "feat: x")}
            p = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                               capture_output=True, text=True)
            self.assertEqual(p.returncode, 0)

    def test_fail_closed_on_unparseable_pr_signal(self):
        # unbalanced quote NOT from a heredoc -> shlex still fails after stripping;
        # it looks like a PR create we can't verify -> block (fail toward guarding).
        with tempfile.TemporaryDirectory() as tmp:
            code, err = run("gh pr create --title 'unterminated", make_repo(tmp, "feat: x"))
            self.assertEqual(code, 2)
            self.assertIn("BLOCKED", err)

    def test_fail_open_on_unparseable_without_pr_signal(self):
        # unparseable but no PR signal -> not the gate's business -> allow.
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(run("echo 'unterminated", make_repo(tmp, "feat: x"))[0], 0)

    def test_bad_payload_is_silent(self):
        p = subprocess.run([sys.executable, str(HOOK)], input="not json",
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0)


class StripHeredocs(unittest.TestCase):
    def test_body_removed_and_command_parses(self):
        import shlex
        stripped = gate.strip_heredocs(HEREDOC_CREATE)
        self.assertNotIn("section's", stripped)          # body gone
        self.assertIn("gh pr create", stripped)          # command kept
        shlex.split(stripped)                            # no ValueError

    def test_noop_without_heredoc(self):
        self.assertEqual(gate.strip_heredocs("gh pr create -f"), "gh pr create -f")


class LooksLikePrCreate(unittest.TestCase):
    def test_true_for_creates(self):
        for c in ["gh pr create", "gh -R o/r pr create", "gh api repos/o/r/pulls -f x=y"]:
            self.assertTrue(gate.looks_like_pr_create(c), c)

    def test_false_for_non_creates(self):
        for c in ["git status", "echo hi", "gh pr view 3"]:
            self.assertFalse(gate.looks_like_pr_create(c), c)


class PrBase(unittest.TestCase):
    def test_detects_create_and_base(self):
        self.assertEqual(gate.pr_base(["gh", "pr", "create", "--base", "dev"]), (True, "dev"))
        self.assertEqual(gate.pr_base(["gh", "pr", "create"]), (True, None))
        self.assertEqual(gate.pr_base(["git", "push"]), (False, None))


if __name__ == "__main__":
    unittest.main()
