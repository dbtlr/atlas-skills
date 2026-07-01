"""Hermetic tests for skills/start-session/build_primer.py.

No external deps (stdlib unittest). Each test builds a throwaway vault under a
temp dir and points the script at it via the ATLAS_PATH env var and an explicit
start directory, so the real atlas vault is never touched.

Run: python3 -m unittest discover -s tests
"""
import contextlib
import io
import os
import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

SKILL_DIR = Path(__file__).resolve().parent.parent / "skills" / "start-session"
sys.path.insert(0, str(SKILL_DIR))
import build_primer  # noqa: E402


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class BuildPrimerTest(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.vault = self.tmp / "vault"
        self.repo = self.tmp / "repo"
        self.repo.mkdir(parents=True)
        self._prev_atlas = os.environ.get("ATLAS_PATH")
        os.environ["ATLAS_PATH"] = str(self.vault)

    def tearDown(self):
        if self._prev_atlas is None:
            os.environ.pop("ATLAS_PATH", None)
        else:
            os.environ["ATLAS_PATH"] = self._prev_atlas
        self._tmp.cleanup()

    # --- fixtures ---
    def write_binding(self, workspace="demo"):
        lines = []
        if workspace is not None:
            lines.append(f'workspace = "{workspace}"')
        write(self.repo / ".atlas.toml", "\n".join(lines) + "\n")

    def write_active_context(self, workspace="demo"):
        ws = self.vault / "Workspaces"
        write(ws / "shared" / "user.md", "# User\nuser-profile-body")
        write(ws / "shared" / "memory.md", "# Memory\nshared-memory-body")
        write(ws / workspace / f"{workspace}.md", "# Brief\nworkspace-brief-body")

    def run_main(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = build_primer.main(["build_primer.py", str(self.repo)])
        return rc, out.getvalue(), err.getvalue()

    # --- tests ---
    def test_happy_path_merges_active_context(self):
        self.write_binding()
        self.write_active_context()
        rc, out, err = self.run_main()
        self.assertEqual(rc, 0, err)
        self.assertIn("Atlas Session Primer — demo", out)
        self.assertIn("user-profile-body", out)
        self.assertIn("shared-memory-body", out)
        self.assertIn("workspace-brief-body", out)

    def test_uninitialized_when_no_binding(self):
        rc, out, _ = self.run_main()
        self.assertEqual(rc, 0)
        self.assertIn("ATLAS_UNINITIALIZED", out)

    def test_no_binding_exits_quietly_even_without_atlas_path(self):
        os.environ.pop("ATLAS_PATH", None)
        rc, out, _ = self.run_main()
        self.assertEqual(rc, 0)
        self.assertIn("ATLAS_UNINITIALIZED", out)

    def test_binding_missing_workspace(self):
        self.write_binding(workspace=None)
        rc, _, err = self.run_main()
        self.assertEqual(rc, 2)
        self.assertIn("must set `workspace`", err)

    def test_atlas_path_unset_is_reported(self):
        self.write_binding()
        os.environ.pop("ATLAS_PATH", None)
        rc, _, err = self.run_main()
        self.assertEqual(rc, 3)
        self.assertIn("ATLAS_PATH is not set", err)

    def test_missing_active_context_file_is_flagged(self):
        self.write_binding()
        self.vault.mkdir(parents=True, exist_ok=True)  # vault exists; the files inside don't
        rc, out, err = self.run_main()
        self.assertEqual(rc, 0, err)
        self.assertIn("(missing: shared/user.md)", out)

    def test_no_mimir_section_without_mimir_toml(self):
        self.write_binding()
        self.write_active_context()
        rc, out, err = self.run_main()
        self.assertEqual(rc, 0, err)
        self.assertNotIn("Work Queue", out)

    def test_atlas_path_nonexistent_dir_is_reported(self):
        self.write_binding()
        os.environ["ATLAS_PATH"] = str(self.tmp / "does-not-exist")
        rc, _, err = self.run_main()
        self.assertEqual(rc, 3)
        self.assertIn("missing directory", err)

    def test_binding_found_by_walking_up_from_subdir(self):
        self.write_binding()
        self.write_active_context()
        sub = self.repo / "a" / "b"
        sub.mkdir(parents=True)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = build_primer.main(["build_primer.py", str(sub)])
        self.assertEqual(rc, 0, err.getvalue())
        self.assertIn("Atlas Session Primer — demo", out.getvalue())

    # --- mimir fold ---
    def _mimir_toml(self):
        (self.repo / ".mimir.toml").write_text("", encoding="utf-8")

    def test_mimir_section_added_when_toml_and_binary_present(self):
        self.write_binding()
        self.write_active_context()
        self._mimir_toml()
        fake = types.SimpleNamespace(returncode=0, stdout="TASK-1 do the thing\n", stderr="")
        with mock.patch.object(build_primer.shutil, "which", return_value="/usr/bin/mimir"), \
             mock.patch.object(build_primer.subprocess, "run", return_value=fake) as run:
            rc, out, err = self.run_main()
        self.assertEqual(rc, 0, err)
        self.assertIn("Work Queue (mimir next)", out)
        self.assertIn("TASK-1 do the thing", out)
        self.assertEqual(run.call_args.kwargs.get("cwd"), self.repo.resolve())

    def test_mimir_section_skipped_on_nonzero_exit(self):
        self.write_binding()
        self.write_active_context()
        self._mimir_toml()
        fake = types.SimpleNamespace(returncode=1, stdout="boom", stderr="err")
        with mock.patch.object(build_primer.shutil, "which", return_value="/usr/bin/mimir"), \
             mock.patch.object(build_primer.subprocess, "run", return_value=fake):
            rc, out, _ = self.run_main()
        self.assertEqual(rc, 0)
        self.assertNotIn("Work Queue", out)

    def test_mimir_section_skipped_when_binary_absent(self):
        self.write_binding()
        self.write_active_context()
        self._mimir_toml()
        with mock.patch.object(build_primer.shutil, "which", return_value=None):
            rc, out, _ = self.run_main()
        self.assertEqual(rc, 0)
        self.assertNotIn("Work Queue", out)


if __name__ == "__main__":
    unittest.main()
