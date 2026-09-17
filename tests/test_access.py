"""SR-13: the file-route helper access record. `access grant` records name, email,
scope (staff|helper) and start date; `access end` records the written deletion
confirmation and refuses without it; `access list` reports the records. The record
lives in the git-ignored workspace/access.json.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import impactos_support as support
from impactos_agent import cli


def _run(command_func, **kwargs):
    return command_func(support.ns(**kwargs))


def _grant(project, name="Dana Helper", email="dana.helper@example.org", scope="helper", start="2026-06-01"):
    return _run(cli.cmd_access_grant, name=name, email=email, scope=scope, start=start, project_root=project)


def _access_json(project):
    return support.load_json(project / "workspace" / "access.json")


class GrantTests(unittest.TestCase):
    def test_grant_records_name_email_scope_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            support.run("init", project_root=project)
            result = _grant(project)
            self.assertEqual(result.exit_code, 0, msg=result.errors)
            grants = _access_json(project)["grants"]
            self.assertEqual(len(grants), 1)
            entry = grants[0]
            self.assertEqual(entry["name"], "Dana Helper")
            self.assertEqual(entry["email"], "dana.helper@example.org")
            self.assertEqual(entry["scope"], "helper")
            self.assertEqual(entry["start"], "2026-06-01")
            self.assertEqual(entry["status"], "active")

    def test_grant_requires_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            support.run("init", project_root=project)
            result = _run(cli.cmd_access_grant, name="Dana Helper", email="dana.helper@example.org", scope=None, start="2026-06-01", project_root=project)
            self.assertEqual(result.exit_code, 1)
            self.assertTrue(any("scope" in e for e in result.errors), msg=result.errors)

    def test_grant_rejects_unknown_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            support.run("init", project_root=project)
            result = _run(cli.cmd_access_grant, name="Dana Helper", email="dana.helper@example.org", scope="admin", start="2026-06-01", project_root=project)
            self.assertEqual(result.exit_code, 1)

    def test_staff_scope_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            support.run("init", project_root=project)
            result = _grant(project, name="Sam Staff", email="sam.staff@example.org", scope="staff")
            self.assertEqual(result.exit_code, 0, msg=result.errors)


class EndTests(unittest.TestCase):
    def test_end_without_confirmation_exits_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            support.run("init", project_root=project)
            _grant(project)
            result = _run(
                cli.cmd_access_end, name="Dana Helper",
                deletion_confirmed_by=None, confirmed_at=None, confirmation_text=None,
                project_root=project,
            )
            self.assertEqual(result.exit_code, 1)
            # The grant is untouched.
            self.assertEqual(_access_json(project)["grants"][0]["status"], "active")

    def test_end_with_partial_confirmation_exits_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            support.run("init", project_root=project)
            _grant(project)
            result = _run(
                cli.cmd_access_end, name="Dana Helper",
                deletion_confirmed_by="Matt", confirmed_at="2026-09-16", confirmation_text=None,
                project_root=project,
            )
            self.assertEqual(result.exit_code, 1)

    def test_end_with_written_confirmation_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            support.run("init", project_root=project)
            _grant(project)
            result = _run(
                cli.cmd_access_end, name="Dana Helper",
                deletion_confirmed_by="Matt Cooper", confirmed_at="2026-09-16",
                confirmation_text="Workspace copy deleted from Dana's laptop; confirmed in writing.",
                project_root=project,
            )
            self.assertEqual(result.exit_code, 0, msg=result.errors)
            entry = _access_json(project)["grants"][0]
            self.assertEqual(entry["status"], "ended")
            self.assertEqual(entry["deletion_confirmation"]["confirmed_by"], "Matt Cooper")
            self.assertEqual(entry["deletion_confirmation"]["confirmed_at"], "2026-09-16")
            self.assertIn("confirmed in writing", entry["deletion_confirmation"]["confirmation_text"])

    def test_end_unknown_name_exits_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            support.run("init", project_root=project)
            _grant(project)
            result = _run(
                cli.cmd_access_end, name="Nobody",
                deletion_confirmed_by="Matt", confirmed_at="2026-09-16", confirmation_text="n/a",
                project_root=project,
            )
            self.assertEqual(result.exit_code, 1)


class ListTests(unittest.TestCase):
    def test_list_reports_grants(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            support.run("init", project_root=project)
            _grant(project)
            _grant(project, name="Sam Staff", email="sam.staff@example.org", scope="staff")
            result = _run(cli.cmd_access_list, project_root=project)
            self.assertEqual(result.exit_code, 0, msg=result.errors)
            self.assertEqual(result.data["count"], 2)
            names = {g["name"] for g in result.data["grants"]}
            self.assertEqual(names, {"Dana Helper", "Sam Staff"})


if __name__ == "__main__":
    unittest.main()
