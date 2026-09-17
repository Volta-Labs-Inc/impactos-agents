"""SR-15: the same records and mappings produce a byte-identical hash set across
two independent runs (separate processes). run.json is excluded from the set."""

from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import impactos_support as support

HASH_SET = ["profile.json", "bai-v5.xlsx", "gaps.md", "provenance.json"]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _export_subprocess(project: Path, out: Path) -> int:
    # A separate process => a different hash-seed, proving determinism is real.
    proc = subprocess.run(
        [sys.executable, str(support.CLI_DIR / "run.py"),
         "export", "--period", support.PERIOD,
         "--project-root", str(project), "--out", str(out)],
        capture_output=True, text=True,
    )
    return proc.returncode


class DeterminismTests(unittest.TestCase):
    def test_two_runs_are_byte_identical_over_the_hash_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            support.build_records(project)
            run_a = project / "run-a"
            run_b = project / "run-b"
            self.assertEqual(_export_subprocess(project, run_a), 0)
            self.assertEqual(_export_subprocess(project, run_b), 0)

            table = {}
            for name in HASH_SET:
                a, b = _sha(run_a / name), _sha(run_b / name)
                table[name] = a
                self.assertEqual(a, b, msg=f"{name} differs between runs ({a} != {b})")
            # sanity: the four hashes are distinct files, all present.
            self.assertEqual(len(table), 4)

    def test_run_json_is_excluded_from_the_hash_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            support.build_records(project)
            out = project / "r"
            _export_subprocess(project, out)
            self.assertTrue((out / "run.json").exists())
            self.assertNotIn("run.json", HASH_SET)
            # The export result declares exactly the four hashed files.
            result = support.export(project, out=project / "r2")
            self.assertEqual(sorted(result.data["hash_set"]), sorted(HASH_SET))


if __name__ == "__main__":
    unittest.main()
