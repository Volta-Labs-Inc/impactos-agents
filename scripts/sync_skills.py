#!/usr/bin/env python3
"""Mirror the ``skills/`` source of truth into every harness skills directory.

One set of skills, authored under ``skills/``, is copied verbatim into
``.claude/skills/`` (Claude Code, Cowork) and ``.agents/skills/`` (Codex, other
harnesses) so a helper gets the same behaviour whichever tool they open. The
source is authoritative; the mirrors are generated.

Usage:

    python scripts/sync_skills.py            # write the mirrors from skills/
    python scripts/sync_skills.py --check    # exit non-zero if a mirror drifted

``--check`` is wired into ``make check`` so CI fails on drift. The sync only
manages the skill names that exist under ``skills/``; unrelated entries in a
mirror (for example symlinked template skills) are left untouched.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRNAME = "skills"
MIRROR_DIRNAMES = [".claude/skills", ".agents/skills"]


def _source_skills(root: Path) -> List[str]:
    source = root / SOURCE_DIRNAME
    if not source.exists():
        return []
    return sorted(p.name for p in source.iterdir() if p.is_dir() and not p.name.startswith("."))


def _skill_files(skill_dir: Path) -> Dict[str, bytes]:
    """Relative path -> bytes for every file in a skill directory."""
    files: Dict[str, bytes] = {}
    for path in sorted(skill_dir.rglob("*")):
        if path.is_file():
            files[path.relative_to(skill_dir).as_posix()] = path.read_bytes()
    return files


def sync(root: Path = REPO_ROOT) -> List[str]:
    """Copy every source skill into each mirror. Returns the actions taken."""
    actions: List[str] = []
    source = root / SOURCE_DIRNAME
    for name in _source_skills(root):
        src = source / name
        for mirror_name in MIRROR_DIRNAMES:
            dst = root / mirror_name / name
            if dst.exists() or dst.is_symlink():
                shutil.rmtree(dst) if dst.is_dir() and not dst.is_symlink() else dst.unlink()
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src, dst)
            actions.append(f"{mirror_name}/{name}")
    return actions


def check(root: Path = REPO_ROOT) -> List[str]:
    """Return a list of drift problems; empty means the mirrors are in sync."""
    problems: List[str] = []
    source = root / SOURCE_DIRNAME
    for name in _source_skills(root):
        want = _skill_files(source / name)
        for mirror_name in MIRROR_DIRNAMES:
            dst = root / mirror_name / name
            if not dst.exists():
                problems.append(f"missing mirror: {mirror_name}/{name}")
                continue
            have = _skill_files(dst)
            if have != want:
                missing = sorted(set(want) - set(have))
                extra = sorted(set(have) - set(want))
                changed = sorted(f for f in (set(want) & set(have)) if want[f] != have[f])
                detail = []
                if missing:
                    detail.append(f"missing {missing}")
                if extra:
                    detail.append(f"extra {extra}")
                if changed:
                    detail.append(f"changed {changed}")
                problems.append(f"drift in {mirror_name}/{name}: " + "; ".join(detail))
    return problems


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report drift and exit non-zero instead of writing")
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="repository root (default: this repo)")
    args = parser.parse_args(argv)

    if args.check:
        problems = check(args.root)
        if problems:
            sys.stderr.write("skills mirror drift detected:\n")
            for problem in problems:
                sys.stderr.write(f"  - {problem}\n")
            sys.stderr.write("Run: python scripts/sync_skills.py\n")
            return 1
        print("skills mirrors in sync")
        return 0

    actions = sync(args.root)
    print(f"synced {len(actions)} mirror path(s):")
    for action in actions:
        print(f"  {action}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
