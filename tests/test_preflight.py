"""Preflight proof (issue #4 matrix): a missing/too-old interpreter or an
unwritable workspace produces a clear, actionable instruction and a non-zero
exit, so the preflight skill can stop and tell the helper exactly what to fix.

The interpreter check reads ``sys.version_info`` at call time, so the
"no Python 3.9+" case is shimmed by pinning that value for one call.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import impactos_support as support
from impactos_agent import workspace


class PreflightMissingInterpreterTests(unittest.TestCase):
    def test_old_interpreter_fails_with_clear_instruction(self):
        original = workspace.sys.version_info
        workspace.sys.version_info = (3, 8, 0, "final", 0)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                result = workspace.preflight(Path(tmp))
        finally:
            workspace.sys.version_info = original
        self.assertNotEqual(result.exit_code, 0)
        self.assertFalse(result.data["python_ok"])
        self.assertTrue(any("3.9" in e for e in result.errors), msg=result.errors)

    def test_healthy_environment_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = support.run("preflight", project_root=Path(tmp))
            self.assertEqual(result.exit_code, 0, msg=result.errors)
            self.assertTrue(result.data["python_ok"])
            self.assertTrue(result.data["workspace_writable"])


if __name__ == "__main__":
    unittest.main()
