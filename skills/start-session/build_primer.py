#!/usr/bin/env python3
"""Build the Atlas Session Primer.

Resolves the per-repo Project Binding (`.atlas.toml`, which names the
`workspace`) against the atlas vault at `$ATLAS_PATH`, and merges the Active
Context — User Profile (`user.md`), Shared Memory (`memory.md`), and the
Workspace Brief — into a single payload printed to stdout.

If the repo also has a `.mimir.toml` and `mimir` is on PATH, the current work
queue (`mimir next`) is folded in as a final section.

The vault is always the atlas vault; its location comes from the required
`ATLAS_PATH` environment variable (no registry, no per-repo vault config). A
repo with no `.atlas.toml` is simply not an atlas workspace — the script exits
quietly so `start-session` can proceed normally in any repo.

Requires Python 3.11+ (stdlib `tomllib`) or the `tomli` package.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover - older interpreters
    try:
        import tomli as tomllib  # type: ignore
    except ModuleNotFoundError:
        sys.stderr.write("atlas: need Python 3.11+ (tomllib) or the 'tomli' package.\n")
        sys.exit(2)

BINDING_FILENAME = ".atlas.toml"
MIMIR_FILENAME = ".mimir.toml"

# Recommend re-grooming the Brief once it exceeds its groomed baseline by this
# factor. The only fixed constant in the primer-bloat forcing function: the
# per-workspace target itself lives in the Brief frontmatter (`brief_baseline`,
# stamped by consolidate-workspace), so it scales with each project's durable
# complexity and the two budgets cannot drift.
BRIEF_BLOAT_MARGIN = 1.2

_BASELINE_RE = re.compile(r"^brief_baseline\s*:\s*[\"']?(\d+)", re.MULTILINE)


def find_binding(start: Path) -> Path | None:
    """Walk up from `start` looking for the per-repo Project Binding."""
    for d in (start, *start.parents):
        candidate = d / BINDING_FILENAME
        if candidate.is_file():
            return candidate
    return None


def load_toml(path: Path) -> dict:
    with path.open("rb") as fh:
        return tomllib.load(fh)


def read_optional(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def parse_brief_baseline(brief_text: str | None) -> int | None:
    """Read the groomed-size baseline stamped in the Brief frontmatter.

    consolidate-workspace writes `brief_baseline: <chars>` after grooming; the
    primer budgets the current Brief against it. Only a value inside the leading
    `---` frontmatter block is trusted. Returns None when the Brief has no
    frontmatter baseline (never consolidated) or it can't be parsed.
    """
    if not brief_text or not brief_text.startswith("---"):
        return None
    end = brief_text.find("\n---", 3)
    if end == -1:
        return None
    m = _BASELINE_RE.search(brief_text[:end])
    return int(m.group(1)) if m else None


def brief_hygiene_banner(brief_text: str | None) -> str | None:
    """A soft, non-blocking recommendation to groom the Workspace Brief.

    Self-calibrating: consolidate-workspace stamps the groomed Brief size as the
    per-workspace baseline, and the primer recommends re-grooming once the Brief
    grows past `baseline × BRIEF_BLOAT_MARGIN`. A Brief with no baseline has
    never been consolidated — recommend an initial pass, which seeds the
    baseline. A missing Brief is flagged elsewhere, so there's nothing to budget.
    """
    if brief_text is None:
        return None
    baseline = parse_brief_baseline(brief_text)
    if baseline is None:
        return (
            "> ⚠️ **Primer hygiene** — the Workspace Brief has no recorded "
            "baseline (never consolidated). Run **consolidate-workspace** to "
            "groom it and seed the baseline. _Soft recommendation, non-blocking._"
        )
    current = len(brief_text)
    if current > baseline * BRIEF_BLOAT_MARGIN:
        pct = round(100 * current / baseline)
        return (
            f"> ⚠️ **Primer hygiene** — the Workspace Brief is ~{current} chars, "
            f"{pct}% of its groomed baseline ({baseline}). Run "
            "**consolidate-workspace** to groom it back down. "
            "_Soft recommendation, non-blocking._"
        )
    return None


def section(title: str, body: str | None, missing_hint: str) -> str:
    if body is None:
        return f"## {title}\n\n_(missing: {missing_hint})_\n"
    return f"## {title}\n\n{body.strip()}\n"


def mimir_section(repo_root: Path) -> str | None:
    """If the repo tracks work in Mimir, fold in the current work queue.

    Requires a `.mimir.toml` in the repo root and `mimir` on PATH. Any failure
    (mimir absent, non-zero exit, timeout) skips the section silently — the
    primer must never fail because of the optional work-queue fold.
    """
    if not (repo_root / MIMIR_FILENAME).is_file():
        return None
    if shutil.which("mimir") is None:
        return None
    try:
        proc = subprocess.run(
            ["mimir", "next"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    out = proc.stdout.strip()
    if not out:
        return None
    return f"## Work Queue (mimir next)\n\n{out}\n"


def main(argv: list[str]) -> int:
    cwd = Path(argv[1]).resolve() if len(argv) > 1 else Path.cwd()

    binding_path = find_binding(cwd)
    if binding_path is None:
        # Not an atlas workspace — start-session quietly proceeds.
        print(f"ATLAS_UNINITIALIZED: no {BINDING_FILENAME} found from {cwd}")
        return 0

    binding = load_toml(binding_path)
    workspace = binding.get("workspace")
    if not workspace:
        sys.stderr.write(f"atlas: {binding_path} must set `workspace`.\n")
        return 2

    atlas_path = os.environ.get("ATLAS_PATH")
    if not atlas_path:
        sys.stderr.write(
            "atlas: ATLAS_PATH is not set. Point it at your atlas vault root, "
            "e.g. `export ATLAS_PATH=~/vaults/atlas`.\n"
        )
        return 3

    root = Path(atlas_path).expanduser()
    if not root.is_dir():
        sys.stderr.write(
            f"atlas: ATLAS_PATH points to a missing directory: {root}. "
            "Set it to your atlas vault root.\n"
        )
        return 3

    workspaces_dir = root / "Workspaces"
    shared_dir = workspaces_dir / "shared"
    ws_dir = workspaces_dir / workspace
    repo_root = binding_path.parent

    user_md = read_optional(shared_dir / "user.md")
    memory_md = read_optional(shared_dir / "memory.md")
    brief_md = read_optional(ws_dir / f"{workspace}.md")

    parts: list[str] = []
    banner = brief_hygiene_banner(brief_md)
    if banner is not None:
        parts += [banner, ""]
    parts += [
        f"# Atlas Session Primer — {workspace}",
        "",
        f"_Vault `{root}` · workspace `{workspace}`. This is your Active Context "
        "for the session; everything else is reached by progressive disclosure "
        "into the workspace._",
        "",
        section("User Profile (user.md)", user_md, "shared/user.md"),
        section("Shared Memory (memory.md)", memory_md, "shared/memory.md"),
        section(f"Workspace Brief ({workspace}.md)", brief_md, f"{workspace}/{workspace}.md"),
    ]
    work = mimir_section(repo_root)
    if work is not None:
        parts.append(work)
    print("\n".join(parts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
