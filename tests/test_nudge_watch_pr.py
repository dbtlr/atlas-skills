"""Hermetic tests for skills/watching-a-pr/resources/hooks/nudge-watch-pr.py.

Pins the PostToolUse contract the hook depends on — the Bash output arrives in
`tool_output` (a string) — plus PR-creation detection, URL extraction, and the
unconditional fail-open. No `gh`, no network.

Run: python3 -m unittest discover -s tests
"""
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

HOOK = (Path(__file__).resolve().parent.parent / "skills" / "watching-a-pr"
        / "resources" / "hooks" / "nudge-watch-pr.py")
_spec = importlib.util.spec_from_file_location("nudge_watch_pr", HOOK)
nudge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nudge)


def run(payload):
    """End-to-end: feed a JSON payload on stdin, return (systemMessage or None)."""
    p = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                       capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    if not p.stdout.strip():
        return None
    return json.loads(p.stdout)["systemMessage"]


class CreatesPrTest(unittest.TestCase):
    def test_detects_create_forms(self):
        for cmd in ["gh pr create -f", "gh -R o/r pr create --fill",
                    "gh pr -R o/r create", "git push && gh pr create",
                    "gh api repos/o/r/pulls -f title=x -f head=h -f base=main"]:
            self.assertTrue(nudge.creates_pr(cmd), cmd)

    def test_ignores_non_creations(self):
        for cmd in ["gh pr view 42", "gh pr create --help", "gh pr create -h",
                    "git commit -m 'gh pr create'", "echo gh pr create",
                    "gh pr list", "gh api repos/o/r/issues"]:
            self.assertFalse(nudge.creates_pr(cmd), cmd)


class OutputTextTest(unittest.TestCase):
    def test_reads_tool_output_string(self):
        self.assertEqual(nudge.output_text({"tool_output": "hi"}), "hi")

    def test_never_crashes_on_odd_shapes(self):
        # a hook must fail open on any payload shape it wasn't expecting
        for payload in [{}, {"tool_output": None}, {"tool_output": 42},
                        {"tool_output": {"stdout": "u", "code": 0}}]:
            self.assertIsInstance(nudge.output_text(payload), str)


class UrlTest(unittest.TestCase):
    def test_generalizes_host_and_takes_last_url(self):
        self.assertEqual(nudge.PR_URL.findall("https://github.com/o/r/pull/42"), ["42"])
        self.assertEqual(nudge.PR_URL.findall("https://github.corp.io/o/r/pull/7"), ["7"])
        # a body-referenced URL first, the created URL last -> take the last
        text = "Follow-up to https://github.com/o/r/pull/7\nhttps://github.com/o/r/pull/42"
        self.assertEqual(nudge.PR_URL.findall(text)[-1], "42")


class EndToEndTest(unittest.TestCase):
    def test_nudges_on_create_with_url(self):
        msg = run({"tool_name": "Bash", "tool_input": {"command": "gh pr create -f"},
                   "tool_output": "https://github.com/o/r/pull/42"})
        self.assertIn("PR #42", msg)

    def test_enterprise_host_still_nudges(self):
        msg = run({"tool_name": "Bash", "tool_input": {"command": "gh -R o/r pr create"},
                   "tool_output": "https://github.mycorp.com/o/r/pull/9\n"})
        self.assertIn("PR #9", msg)

    def test_silent_on_view(self):
        self.assertIsNone(run({"tool_name": "Bash",
                               "tool_input": {"command": "gh pr view 42"},
                               "tool_output": "https://github.com/o/r/pull/42"}))

    def test_silent_when_create_produced_no_url(self):
        self.assertIsNone(run({"tool_name": "Bash",
                               "tool_input": {"command": "gh pr create -f"},
                               "tool_output": "error: something went wrong"}))

    def test_fail_open_on_wrong_field_and_odd_payloads(self):
        # the exact bug this file exists to catch: output under a wrong/absent field
        self.assertIsNone(run({"tool_name": "Bash",
                               "tool_input": {"command": "gh pr create -f"},
                               "tool_result": "https://github.com/o/r/pull/42"}))
        self.assertIsNone(run({"tool_name": "Bash",
                               "tool_input": {"command": "gh pr create"},
                               "tool_output": {"stdout": "x"}}))  # dict, no URL -> silent
        self.assertIsNone(run({"not": "a hook payload"}))

    def test_non_bash_tool_is_silent(self):
        self.assertIsNone(run({"tool_name": "Read", "tool_input": {}, "tool_output": "x"}))


if __name__ == "__main__":
    unittest.main()
