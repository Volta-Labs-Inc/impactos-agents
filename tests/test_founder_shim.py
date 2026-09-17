"""The founder shim exposes only ``submit`` and ``status``, lands submissions as
``pending``, and never touches a fact table (that is 6a's job to deny and the
guarded acceptance function's job to allow)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import impactos_support  # noqa: F401  (puts cli/ on sys.path)
from impactos_agent import founder

COMPANY = "2a2a2a2a-0000-4000-8000-0000000000aa"


def _project() -> Path:
    root = Path(tempfile.mkdtemp())
    (root / "workspace").mkdir()
    return root


class SurfaceTests(unittest.TestCase):
    def test_only_submit_and_status_are_exposed(self):
        parser = founder.build_parser()
        actions = [a for a in parser._actions if hasattr(a, "choices") and a.choices]
        commands = set()
        for action in actions:
            commands.update(action.choices or {})
        self.assertEqual(commands, {"submit", "status"})


class SubmitTests(unittest.TestCase):
    def _fields_file(self, root) -> Path:
        path = root / "fields.json"
        path.write_text(json.dumps({"fields": [
            {"field_class": "metric", "fact_table": "company_update",
             "record": {"source_system": "founder", "source_id": "u-1",
                        "update_date": "2026-03-31", "current_ftes": 7}}
        ]}), encoding="utf-8")
        return path

    def test_submit_posts_a_pending_submission_with_the_payload(self):
        root = _project()
        fields = self._fields_file(root)
        captured = {}

        def fake_authed(project_root, method, path, body=None):
            captured["method"] = method
            captured["path"] = path
            captured["body"] = body
            return 201, json.dumps([{"id": "sub-1", "status": "pending"}]).encode()

        with mock.patch.object(founder.store_mod, "authed_request", side_effect=fake_authed):
            result = founder.submit(root, SimpleNamespace(
                company=COMPANY, fields=str(fields), source_id="s-1", channel=None, json=False))

        self.assertEqual(result.verdict, "pass", result.errors)
        self.assertEqual(captured["method"], "POST")
        self.assertIn("/rest/v1/submission", captured["path"])
        self.assertEqual(captured["body"]["status"], "pending")
        self.assertEqual(captured["body"]["company_id"], COMPANY)
        payload = json.loads(captured["body"]["raw_payload_ref"])
        self.assertEqual(payload["fields"][0]["field_class"], "metric")

    def test_submit_refuses_a_bad_company(self):
        root = _project()
        fields = self._fields_file(root)
        result = founder.submit(root, SimpleNamespace(
            company="nope", fields=str(fields), source_id=None, channel=None, json=False))
        self.assertEqual(result.verdict, "fail")

    def test_submit_refuses_without_fields(self):
        root = _project()
        result = founder.submit(root, SimpleNamespace(
            company=COMPANY, fields=None, source_id=None, channel=None, json=False))
        self.assertEqual(result.verdict, "fail")


class StatusTests(unittest.TestCase):
    def test_status_lists_submissions_by_state(self):
        root = _project()

        def fake_authed(project_root, method, path, body=None):
            return 200, json.dumps([
                {"id": "1", "source_id": "a", "status": "pending", "channel": "shim",
                 "submitted_at": "2026-03-20", "company_id": COMPANY},
                {"id": "2", "source_id": "b", "status": "accepted", "channel": "shim",
                 "submitted_at": "2026-03-21", "company_id": COMPANY},
            ]).encode()

        with mock.patch.object(founder.store_mod, "authed_request", side_effect=fake_authed):
            result = founder.status(root, SimpleNamespace(json=False))
        self.assertEqual(result.verdict, "pass", result.errors)
        self.assertEqual(result.data["by_status"], {"pending": 1, "accepted": 1})


if __name__ == "__main__":
    unittest.main()
