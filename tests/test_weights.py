"""Tests for skills/consolidate-memory/weights.py (stdlib unittest, no deps).

Run: python3 -m unittest discover -s tests
"""
import contextlib
import io
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

SKILL_DIR = Path(__file__).resolve().parent.parent / "skills" / "consolidate-memory"
sys.path.insert(0, str(SKILL_DIR))
import weights  # noqa: E402

NOW = date(2026, 7, 1)

# A ledger with: the format spec (a fenced ### example that must be ignored) and a
# ## Clusters section holding five clusters exercising every tier + archived skip.
LEDGER = """\
---
title: Observations
type: observations
---

# Observations

## Entry format

### How to write (this heading precedes Clusters and must be ignored)

```markdown
### Fenced example — must never be parsed as a cluster
- **bucket:** memory
- **status:** active
- **evidence:**
  - 2026-06-30 | ghost | [[should-not-appear]]
```

## Clusters

### Strong cross-project pattern
- **bucket:** memory
- **status:** active
- **evidence:**
  - 2026-06-30 | atlas-skills | [[log-a1]]
  - 2026-06-28 | atlas-skills | [[log-a3]]
  - 2026-06-20 | mimir | [[log-a2]]

### Aging single-workspace pattern
- **bucket:** user
- **status:** active
- **evidence:**
  - 2026-06-25 | tyr | [[log-b1]]

### Stale old pattern
- **bucket:** memory
- **status:** active
- **evidence:**
  - 2025-12-01 | norn | [[log-c1]]

### Archived pattern
- **bucket:** memory
- **status:** archived
- **evidence:**
  - 2026-06-30 | atlas-skills | [[log-d1]]

### Decay boundary pattern
- bucket: user
- status: active
- evidence:
  - 2026-04-02 | valhalla | [[log-e1]]
"""


class ParseTest(unittest.TestCase):
    def test_ignores_fenced_example_and_pre_clusters_headings(self):
        clusters = weights.parse_clusters(LEDGER)
        headings = [c.heading for c in clusters]
        # all five real clusters (incl. archived), none from the fenced example
        self.assertEqual(len(clusters), 5)
        self.assertNotIn("Fenced example — must never be parsed as a cluster", headings)
        self.assertIn("Strong cross-project pattern", headings)

    def test_fields_and_evidence_parsed(self):
        a = weights.parse_clusters(LEDGER)[0]
        self.assertEqual(a.bucket, "memory")
        self.assertEqual(a.status, "active")
        self.assertEqual(len(a.evidence), 3)
        self.assertEqual(a.evidence[0], ("2026-06-30", "atlas-skills", "log-a1"))

    def test_non_bold_fields_parsed(self):
        e = [c for c in weights.parse_clusters(LEDGER) if c.heading == "Decay boundary pattern"][0]
        self.assertEqual(e.bucket, "user")
        self.assertEqual(e.status, "active")

    def test_empty_ledger(self):
        self.assertEqual(weights.parse_clusters("# Observations\n\n## Clusters\n\n<!-- empty -->\n"), [])
        self.assertEqual(weights.parse_clusters("no clusters heading at all"), [])

    def test_fence_inside_clusters_section_ignored(self):
        # a fenced ### that appears WITHIN the Clusters section (exercises in_fence,
        # not just the section boundary)
        text = (
            "## Clusters\n\n"
            "### Real cluster\n- **status:** active\n- **evidence:**\n"
            "  - 2026-06-30 | ws | [[log]]\n\n"
            "```markdown\n### Fenced not-a-cluster\n- **bucket:** memory\n```\n"
        )
        headings = [c.heading for c in weights.parse_clusters(text)]
        self.assertEqual(headings, ["Real cluster"])

    def test_malformed_date_dropped_not_crash(self):
        text = (
            "## Clusters\n\n### C\n- **evidence:**\n"
            "  - 2026-13-45 | ws | [[bad]]\n"      # month 13 / day 45 → invalid
            "  - 2026-06-30 | ws | [[good]]\n"
        )
        c = weights.parse_clusters(text)[0]
        self.assertEqual([e[2] for e in c.evidence], ["good"])  # bad-date line dropped


class ScoreTest(unittest.TestCase):
    def test_decay_at_exact_half_life(self):
        # single hit exactly 90 days before NOW → decay 0.5, spread 1 → weight 0.5
        e = [c for c in weights.parse_clusters(LEDGER) if c.heading == "Decay boundary pattern"][0]
        r = weights.score(e, NOW)
        self.assertEqual(r["weight"], 0.5)
        self.assertEqual(r["newest_date"], "2026-04-02")

    def test_spread_counts_distinct_workspaces(self):
        a = weights.parse_clusters(LEDGER)[0]
        r = weights.score(a, NOW)
        self.assertEqual(r["spread"], 2)   # atlas-skills, mimir (dedup)
        self.assertEqual(r["count"], 3)    # three evidence lines

    def test_tiers(self):
        by = {c.heading: weights.score(c, NOW) for c in weights.parse_clusters(LEDGER)}
        self.assertEqual(by["Strong cross-project pattern"]["tier"], "strong")   # recent + spread≥2
        self.assertEqual(by["Aging single-workspace pattern"]["tier"], "aging")  # recent but spread 1
        self.assertEqual(by["Decay boundary pattern"]["tier"], "aging")          # age 90 but spread 1
        self.assertEqual(by["Stale old pattern"]["tier"], "stale")               # newest > 180d

    def test_future_date_does_not_amplify(self):
        c = weights.Cluster(heading="future", evidence=[("2026-12-31", "x", "l")])
        r = weights.score(c, NOW)
        self.assertLessEqual(r["weight"], 1.0)  # clamped: no decay > 1

    def test_strong_cluster_weight_value(self):
        # spread 2 × (decay(1)+decay(3)+decay(11)) = 2 × 2.888257… = 5.777 (3dp)
        a = weights.parse_clusters(LEDGER)[0]
        self.assertEqual(weights.score(a, NOW)["weight"], 5.777)

    def test_stale_boundary_180_vs_181(self):
        at_180 = (NOW - timedelta(days=180)).isoformat()
        at_181 = (NOW - timedelta(days=181)).isoformat()
        c180 = weights.Cluster(heading="x", evidence=[(at_180, "a", "l"), (at_180, "b", "l2")])
        c181 = weights.Cluster(heading="y", evidence=[(at_181, "a", "l"), (at_181, "b", "l2")])
        self.assertEqual(weights.score(c180, NOW)["tier"], "aging")  # exactly 180 → not stale
        self.assertEqual(weights.score(c181, NOW)["tier"], "stale")  # >180 → stale (spread ignored)

    def test_no_evidence_cluster(self):
        r = weights.score(weights.Cluster(heading="empty"), NOW)
        self.assertEqual((r["spread"], r["count"], r["newest_date"], r["weight"], r["tier"]),
                         (0, 0, None, 0, "stale"))


class ComputeTest(unittest.TestCase):
    def test_archived_skipped_and_ranked_by_weight(self):
        rows = weights.compute(LEDGER, NOW)
        headings = [r["heading"] for r in rows]
        self.assertNotIn("Archived pattern", headings)
        self.assertEqual(
            headings,
            [
                "Strong cross-project pattern",   # ~5.8
                "Aging single-workspace pattern", # ~0.95
                "Decay boundary pattern",         # 0.5
                "Stale old pattern",              # ~0.2
            ],
        )

    def test_empty_ledger_is_empty(self):
        self.assertEqual(weights.compute("## Clusters\n", NOW), [])


class CLITest(unittest.TestCase):
    def _run(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = weights.main(["weights.py", *argv])
        return code, out.getvalue(), err.getvalue()

    def test_bad_now_exits_2_no_traceback(self):
        with TemporaryDirectory() as d:
            p = Path(d) / "obs.md"
            p.write_text(LEDGER, encoding="utf-8")
            code, _, err = self._run([str(p), "--now", "notadate"])
        self.assertEqual(code, 2)
        self.assertIn("invalid --now", err)

    def test_missing_file_exits_2(self):
        code, _, err = self._run(["/no/such/observations.md"])
        self.assertEqual(code, 2)
        self.assertIn("not found", err)

    def test_happy_path_json(self):
        with TemporaryDirectory() as d:
            p = Path(d) / "obs.md"
            p.write_text(LEDGER, encoding="utf-8")
            code, out, _ = self._run([str(p), "--now", "2026-07-01", "--format", "json"])
        self.assertEqual(code, 0)
        self.assertIn("Strong cross-project pattern", out)
        self.assertNotIn("Archived pattern", out)


if __name__ == "__main__":
    unittest.main()
