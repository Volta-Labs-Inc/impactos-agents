"""SR-12 (part 1): every path the export/parse/apply flow writes under workspace/
is git-ignored, and only workspace/.gitkeep is committable."""

from __future__ import annotations

import subprocess
import unittest

import impactos_support as support

# Representative of every file children 3-7 write under the workspace tree.
WRITTEN_PATHS = [
    "workspace/sources/2026-06-30/companies.source.json",
    "workspace/state/2026-06-30/records.json",
    "workspace/reports/2026-06-30/profile.json",
    "workspace/reports/2026-06-30/bai-v5.xlsx",
    "workspace/reports/2026-06-30/gaps.md",
    "workspace/reports/2026-06-30/provenance.json",
    "workspace/reports/2026-06-30/run.json",
    "workspace/provenance/2026-06-30.json",
    "workspace/briefs/2026-06-30.md",
    "workspace/evidence/note.txt",
    "workspace/config.json",
    "workspace/access.json",
]


def _ignored(path: str) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "-q", path],
        cwd=str(support.REPO_ROOT), capture_output=True,
    )
    return result.returncode == 0


class GitignoreTests(unittest.TestCase):
    def test_every_written_workspace_path_is_ignored(self):
        for path in WRITTEN_PATHS:
            self.assertTrue(_ignored(path), msg=f"{path} is NOT git-ignored")

    def test_gitkeep_placeholder_is_not_ignored(self):
        self.assertFalse(_ignored("workspace/.gitkeep"))

    def test_gitkeep_is_tracked(self):
        tracked = subprocess.run(
            ["git", "ls-files", "workspace/.gitkeep"],
            cwd=str(support.REPO_ROOT), capture_output=True, text=True,
        ).stdout.strip()
        self.assertEqual(tracked, "workspace/.gitkeep")

    def test_no_workspace_file_other_than_gitkeep_is_tracked(self):
        tracked = subprocess.run(
            ["git", "ls-files", "workspace/"],
            cwd=str(support.REPO_ROOT), capture_output=True, text=True,
        ).stdout.split()
        self.assertEqual(tracked, ["workspace/.gitkeep"])


if __name__ == "__main__":
    unittest.main()
