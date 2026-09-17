"""SR-05: the route recommendation follows a fixed rule, a source with no stable
identifier is treated as a missing required field, and the chosen route is
recorded.

The rule the deterministic helper encodes:

* company (and other reference/master data) that lives in an existing system with
  a stable identifier -> stay in that system;
* interactions -> move to the optional store (they have no home system);
* funding -> conditional (stays only if the source keeps dated history with
  stable identifiers and declared amounts);
* any source with no stable identifier -> store-or-add-identifier (the missing
  identifier is a required field).
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import impactos_support as support
from impactos_agent import interview


class RouteRuleTests(unittest.TestCase):
    def test_company_with_identifier_stays(self):
        self.assertEqual(
            interview.recommend_route("company", source_present=True, has_stable_identifier=True)["recommendation"],
            "stay",
        )

    def test_interaction_stores(self):
        self.assertEqual(
            interview.recommend_route("interaction", source_present=True, has_stable_identifier=True)["recommendation"],
            "store",
        )

    def test_funding_is_conditional(self):
        self.assertEqual(
            interview.recommend_route("funding_event", source_present=True, has_stable_identifier=True)["recommendation"],
            "conditional",
        )

    def test_no_identifier_source_is_store_or_add_id(self):
        result = interview.recommend_route("company", source_present=True, has_stable_identifier=False)
        self.assertEqual(result["recommendation"], "store_or_add_identifier")
        self.assertIn("stable_identifier", result["missing_fields"])

    def test_no_identifier_gate_beats_class(self):
        # Even an interaction without a stable identifier is store-or-add-id, so the
        # missing-field gate is evaluated before the data-type class.
        result = interview.recommend_route("interaction", source_present=True, has_stable_identifier=False)
        self.assertEqual(result["recommendation"], "store_or_add_identifier")

    def test_absent_source_stores(self):
        result = interview.recommend_route("interaction", source_present=False, has_stable_identifier=False)
        self.assertEqual(result["recommendation"], "store")


class RouteCommandTests(unittest.TestCase):
    def _source_map(self, tmp: Path) -> Path:
        source_map = {
            "source_map_version": "1.0.0",
            "data_types": {
                "company": {"present": True, "source": "harbourline-crm", "has_stable_identifier": True},
                "interaction": {"present": True, "source": "fathom-export", "has_stable_identifier": True},
                "funding_event": {"present": True, "source": "founder-os", "has_stable_identifier": True},
                "milestone_position": {"present": True, "source": "spreadsheet", "has_stable_identifier": False},
            },
        }
        path = tmp / "source-map.json"
        path.write_text(json.dumps(source_map, indent=2), encoding="utf-8")
        return path

    def test_route_command_recommends_per_type_and_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            source_map = self._source_map(project)
            result = support.run(
                "interview", action="route", id=None, value=None,
                questions=None, source_map=str(source_map), project_root=project,
            )
            self.assertEqual(result.exit_code, 0, msg=result.errors)
            recs = {r["data_type"]: r["recommendation"] for r in result.data["routes"]}
            self.assertEqual(recs["company"], "stay")
            self.assertEqual(recs["interaction"], "store")
            self.assertEqual(recs["funding_event"], "conditional")
            self.assertEqual(recs["milestone_position"], "store_or_add_identifier")

            # The recommendation set is recorded to a deterministic artifact so the
            # onboarding skill can turn it into operating-notes/routes.md.
            recorded = project / "workspace" / "state" / "route.json"
            self.assertTrue(recorded.exists())
            saved = json.loads(recorded.read_text(encoding="utf-8"))
            self.assertEqual(
                {r["data_type"] for r in saved["routes"]},
                {"company", "interaction", "funding_event", "milestone_position"},
            )

    def test_chosen_route_recorded_and_compared(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            source_map = {
                "source_map_version": "1.0.0",
                "data_types": {
                    "company": {"present": True, "source": "crm", "has_stable_identifier": True, "route": "store"},
                },
            }
            path = project / "source-map.json"
            path.write_text(json.dumps(source_map), encoding="utf-8")
            result = support.run(
                "interview", action="route", id=None, value=None,
                questions=None, source_map=str(path), project_root=project,
            )
            row = result.data["routes"][0]
            self.assertEqual(row["recommendation"], "stay")
            self.assertEqual(row["chosen_route"], "store")
            self.assertFalse(row["matches_recommendation"])


if __name__ == "__main__":
    unittest.main()
