"""The skills source of truth is ``skills/``; it is mirrored into
``.claude/skills/`` and ``.agents/skills/`` so every harness sees the same
skills. ``make check`` runs ``sync_skills.py --check`` and fails on drift.

These tests drive the sync helper on a temporary tree and also assert the real
repository mirrors are in sync.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "sync_skills.py"

spec = importlib.util.spec_from_file_location("sync_skills", SCRIPT)
sync_skills = importlib.util.module_from_spec(spec)
sys.modules["sync_skills"] = sync_skills
spec.loader.exec_module(sync_skills)


def _make_skill(root: Path, name: str, body: str = "# skill\n") -> None:
    skill = root / "skills" / name
    skill.mkdir(parents=True, exist_ok=True)
    (skill / "SKILL.md").write_text(body, encoding="utf-8")


class SyncTests(unittest.TestCase):
    def test_sync_creates_both_mirrors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_skill(root, "onboarding")
            sync_skills.sync(root)
            for mirror in (".claude/skills", ".agents/skills"):
                self.assertTrue((root / mirror / "onboarding" / "SKILL.md").exists())
            self.assertEqual(sync_skills.check(root), [])

    def test_check_detects_content_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_skill(root, "onboarding")
            sync_skills.sync(root)
            (root / ".claude/skills/onboarding/SKILL.md").write_text("drift\n", encoding="utf-8")
            problems = sync_skills.check(root)
            self.assertTrue(problems)
            self.assertTrue(any("onboarding" in p for p in problems))

    def test_check_detects_missing_mirror(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_skill(root, "onboarding")
            sync_skills.sync(root)
            (root / ".agents/skills/onboarding/SKILL.md").unlink()
            self.assertTrue(sync_skills.check(root))

    def test_foreign_mirror_entries_are_left_alone(self):
        # Symlinked template skills already present in .claude/skills must not be
        # reported as drift or removed: sync only manages names under skills/.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_skill(root, "onboarding")
            foreign = root / ".claude/skills/template-skill"
            foreign.mkdir(parents=True)
            (foreign / "SKILL.md").write_text("external\n", encoding="utf-8")
            sync_skills.sync(root)
            self.assertEqual(sync_skills.check(root), [])
            self.assertTrue((foreign / "SKILL.md").exists())


class RealRepoMirrorTests(unittest.TestCase):
    def test_committed_mirrors_match_source(self):
        self.assertEqual(sync_skills.check(REPO_ROOT), [], msg="run: python scripts/sync_skills.py")


if __name__ == "__main__":
    unittest.main()
