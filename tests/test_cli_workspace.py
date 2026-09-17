"""SR-01: `init` creates the workspace tree, config and pre-commit hook with no
database; `preflight` reports the interpreter and a writable workspace; `state`
summarises the workspace."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

import impactos_support as support


def _git_init(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.email", "t@example.org"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=str(path), check=True)


class PreflightTests(unittest.TestCase):
    def test_preflight_reports_interpreter_and_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = support.run("preflight", project_root=Path(tmp))
            self.assertEqual(result.exit_code, 0)
            self.assertTrue(result.data["python_ok"])
            self.assertTrue(result.data["workspace_writable"])
            self.assertEqual(result.data["vendored_openpyxl"], "3.1.5")
            self.assertTrue(result.data["bundled_template_present"])


class InitTests(unittest.TestCase):
    def test_init_creates_tree_config_and_hook_no_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            _git_init(project)
            # bin/impactos lives in the real repo; the hook resolves it at commit.
            (project / "bin").mkdir()
            result = support.run("init", project_root=project)
            self.assertEqual(result.exit_code, 0, msg=result.errors)

            workspace = project / "workspace"
            self.assertTrue((workspace / "config.json").exists())
            self.assertTrue((workspace / ".gitkeep").exists())
            for sub in ("sources", "reports", "state", "provenance", "briefs", "evidence"):
                self.assertTrue((workspace / sub).is_dir(), msg=f"missing workspace/{sub}")
            # No database of any kind is created.
            self.assertIsNone(result.data["database"])
            self.assertEqual(list(workspace.glob("*.db")), [])
            self.assertEqual(list(workspace.glob("*.sqlite*")), [])

            # Committed directories and source map stubs.
            self.assertTrue((project / "mappings").is_dir())
            self.assertTrue((project / "operating-notes").is_dir())
            self.assertTrue((project / "source-map.json").exists())

            # Pre-commit hook installed and core.hooksPath set.
            hook = project / ".githooks" / "pre-commit"
            self.assertTrue(hook.exists())
            self.assertTrue(hook.stat().st_mode & 0o111, "hook must be executable")
            configured = subprocess.run(
                ["git", "config", "--get", "core.hooksPath"],
                cwd=str(project), capture_output=True, text=True,
            ).stdout.strip()
            self.assertEqual(configured, ".githooks")

    def test_init_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            _git_init(project)
            support.run("init", project_root=project)
            second = support.run("init", project_root=project)
            self.assertEqual(second.exit_code, 0)


class StateTests(unittest.TestCase):
    def test_state_reports_periods_after_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            support.run("init", project_root=project)
            support.build_records(project)
            support.export(project)
            result = support.run("state", project_root=project)
            self.assertTrue(result.data["initialised"])
            self.assertIn(support.PERIOD, result.data["record_periods"])
            self.assertIn(support.PERIOD, result.data["report_periods"])
            self.assertIsNone(result.data["database"])


if __name__ == "__main__":
    unittest.main()
