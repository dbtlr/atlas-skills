#!/usr/bin/env python3
"""Compute per-cluster weights for the observations ledger (consolidate-memory v2).

Parses `Workspaces/shared/observations.md` and, for every **active** cluster,
derives the reconcile weight deterministically so the bias-resistance gate is
*computed*, not eyeballed (ADR 0017; see references/reconcile-rubric.md):

    weight = spread × Σ decay(now − hit_date)
      spread       = distinct workspaces across the cluster's evidence
      decay(Δdays) = 0.5 ** (Δdays / HALF_LIFE_DAYS)      # ~90-day half-life

Tiers are recency-gated (staleness wins over spread):
    stale   — newest hit older than STALE_AGE_DAYS (~180d), regardless of spread
    strong  — newest hit within STRONG_AGE_DAYS (~90d) AND spread ≥ STRONG_MIN_SPREAD
    aging   — everything between

Only the `## Clusters` section is parsed (the format spec and its fenced example
live above it and are ignored). Archived clusters are skipped. Nothing is
written back — weight is derived, never stored.

Usage:
    weights.py [OBSERVATIONS_MD] [--now YYYY-MM-DD] [--format json|table]

OBSERVATIONS_MD defaults to $ATLAS_PATH/Workspaces/shared/observations.md.
Requires Python 3.9+ (stdlib only).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

HALF_LIFE_DAYS = 90
STALE_AGE_DAYS = 180
STRONG_AGE_DAYS = 90
STRONG_MIN_SPREAD = 2

CLUSTERS_HEADING = "## Clusters"

# `  - 2026-06-30 | atlas-skills | [[some-log]]`  → date, workspace, log
_EVIDENCE = re.compile(
    r"^\s*-\s*(\d{4}-\d{2}-\d{2})\s*\|\s*([^|]+?)\s*\|\s*(.+?)\s*$"
)
# `- **bucket:** memory`  or  `- bucket: memory`
_FIELD = re.compile(r"^\s*-\s*\*{0,2}(bucket|status)\*{0,2}\s*:\s*(.+?)\s*$", re.I)


@dataclass
class Cluster:
    heading: str
    bucket: str = ""
    status: str = "active"
    # each hit: (iso_date, workspace, log)
    evidence: list[tuple[str, str, str]] = field(default_factory=list)


def _strip_wikilink(target: str) -> str:
    t = target.strip()
    if t.startswith("[[") and t.endswith("]]"):
        t = t[2:-2]
    return t.strip()


def parse_clusters(text: str) -> list[Cluster]:
    """Parse the `## Clusters` section into Cluster records (all statuses)."""
    lines = text.splitlines()

    # Locate the Clusters section; collect until the next level-2 heading / EOF.
    start = None
    for i, line in enumerate(lines):
        if line.strip() == CLUSTERS_HEADING:
            start = i + 1
            break
    if start is None:
        return []

    clusters: list[Cluster] = []
    current: Cluster | None = None
    in_fence = False
    for line in lines[start:]:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if stripped.startswith("## "):  # next level-2 section ends the region
            break
        if stripped.startswith("### "):
            current = Cluster(heading=stripped[4:].strip())
            clusters.append(current)
            continue
        if current is None:
            continue
        m = _EVIDENCE.match(line)
        if m:
            try:  # defensive (observations.md contract): drop an unparseable date, don't crash
                date.fromisoformat(m.group(1))
            except ValueError:
                continue
            current.evidence.append(
                (m.group(1), m.group(2).strip(), _strip_wikilink(m.group(3)))
            )
            continue
        f = _FIELD.match(line)
        if f:
            # value may trail the field's closing bold marker: `**bucket:** memory`
            key, val = f.group(1).lower(), f.group(2).strip().strip("*").strip()
            if key == "bucket":
                current.bucket = val.lower()
            else:
                current.status = val.lower()
    return clusters


def _decay(age_days: int) -> float:
    return 0.5 ** (max(0, age_days) / HALF_LIFE_DAYS)


def score(cluster: Cluster, now: date) -> dict:
    """Derive spread/count/newest/weight/tier for one cluster."""
    dates = [date.fromisoformat(d) for d, _, _ in cluster.evidence]
    workspaces = {ws for _, ws, _ in cluster.evidence}
    spread = len(workspaces)
    count = len(cluster.evidence)
    weight = spread * sum(_decay((now - d).days) for d in dates)

    newest = max(dates) if dates else None
    newest_age = (now - newest).days if newest else None

    if newest is None or newest_age > STALE_AGE_DAYS:
        tier = "stale"
    elif newest_age <= STRONG_AGE_DAYS and spread >= STRONG_MIN_SPREAD:
        tier = "strong"
    else:
        tier = "aging"

    return {
        "heading": cluster.heading,
        "bucket": cluster.bucket,
        "spread": spread,
        "count": count,
        "newest_date": newest.isoformat() if newest else None,
        "weight": round(weight, 3),
        "tier": tier,
    }


def compute(text: str, now: date) -> list[dict]:
    """Score every ACTIVE cluster, ranked by weight (desc), then spread, then recency."""
    scored = [
        score(c, now) for c in parse_clusters(text) if c.status != "archived"
    ]
    scored.sort(
        key=lambda r: (r["weight"], r["spread"], r["newest_date"] or ""),
        reverse=True,
    )
    return scored


def _default_path() -> Path | None:
    root = os.environ.get("ATLAS_PATH")
    if not root:
        return None
    return Path(root) / "Workspaces" / "shared" / "observations.md"


def _render_table(rows: list[dict]) -> str:
    if not rows:
        return "(no active clusters)"
    head = f"{'weight':>8}  {'tier':<6}  {'spread':>6}  {'count':>5}  {'newest':<10}  {'bucket':<6}  heading"
    out = [head, "-" * len(head)]
    for r in rows:
        out.append(
            f"{r['weight']:>8}  {r['tier']:<6}  {r['spread']:>6}  {r['count']:>5}  "
            f"{(r['newest_date'] or '—'):<10}  {(r['bucket'] or '—'):<6}  {r['heading']}"
        )
    return "\n".join(out)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Compute observations-ledger cluster weights.")
    parser.add_argument("path", nargs="?", help="observations.md (default: $ATLAS_PATH/Workspaces/shared/observations.md)")
    parser.add_argument("--now", help="reference date YYYY-MM-DD (default: today)")
    parser.add_argument("--format", choices=("json", "table"), default="json")
    args = parser.parse_args(argv[1:])

    path = Path(args.path) if args.path else _default_path()
    if path is None:
        sys.stderr.write("weights: no path given and ATLAS_PATH is not set.\n")
        return 2
    if not path.exists():
        sys.stderr.write(f"weights: not found: {path}\n")
        return 2

    if args.now:
        try:
            now = date.fromisoformat(args.now)
        except ValueError:
            sys.stderr.write(f"weights: invalid --now date (want YYYY-MM-DD): {args.now}\n")
            return 2
    else:
        now = date.today()
    rows = compute(path.read_text(encoding="utf-8"), now)

    if args.format == "json":
        print(json.dumps(rows, indent=2))
    else:
        print(_render_table(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
