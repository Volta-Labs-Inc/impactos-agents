"""SR-10: `compare` reports changed / new / absent / unmatched / missing-required
against a prior-period baseline, matching ONLY on the mapping's declared identity
column. A name match never authorises a merge.

Two independent checks guard the same truth:

1. The committed ``expected/compare.json`` deltas are re-derived here directly from
   the two CRM CSVs, so the encoded fixture cannot silently drift from the data.
2. The real ``impactos compare`` command, driven over the parsed-and-mapped
   records for both periods, produces those same deltas per data type.
"""

from __future__ import annotations

import csv
import io
import tempfile
import unittest
from pathlib import Path

import impactos_support as support
from impactos_agent import cli, compare

FIXTURE = support.FIXTURE
CRM_P1 = support.CRM_P1
CRM_P2 = support.CRM_P2
CRM_MAPPING_P2 = support.CRM_MAPPING
CRM_MAPPING_P1 = support.REPO_ROOT / "tests" / "data" / "crm-mapping-p1.json"
EXPECTED = FIXTURE / "expected" / "compare.json"

PERIOD_1 = "2026-03-31"
PERIOD_2 = "2026-06-30"


def _read_csv(path: Path):
    text = path.read_text(encoding="utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def _run(command_func, **kwargs):
    return command_func(support.ns(**kwargs))


def _build_period(project: Path, source: Path, mapping_path: Path, period: str) -> None:
    """Parse a CRM CSV and apply its mapping for the given period."""
    support.parse_source(project, source, period)
    _run(
        cli.cmd_apply_mapping,
        source=str(support.payload_path(project, source, period)),
        mapping=str(mapping_path),
        period=period,
        confirmed=True,
        out=None,
        project_root=project,
    )


def _compare_period_two(project: Path):
    """Set up both periods, establish the p1 baseline, and compare p2 to it."""
    _build_period(project, CRM_P1, CRM_MAPPING_P1, PERIOD_1)
    _run(cli.cmd_compare, period=PERIOD_1, out=None, project_root=project)
    _build_period(project, CRM_P2, CRM_MAPPING_P2, PERIOD_2)
    result = _run(cli.cmd_compare, period=PERIOD_2, out=None, project_root=project)
    comparison = support.load_json(project / "workspace" / "reports" / PERIOD_2 / "compare.json")
    return result, comparison


class FixtureDeltaTests(unittest.TestCase):
    """Re-derive the deltas straight from the CSVs; they must equal the fixture."""

    def test_expected_compare_reproduces_from_csvs(self):
        p1 = {r["record_id"]: r for r in _read_csv(CRM_P1)}
        p2 = {r["record_id"]: r for r in _read_csv(CRM_P2)}
        p1_names = {r["company_name"] for r in p1.values()}
        name_to_p1 = {r["company_name"]: rid for rid, r in p1.items()}

        changed = sorted(
            (
                {"record_id": rid, "from_employees": int(p1[rid]["employees"]), "to_employees": int(p2[rid]["employees"])}
                for rid in p1
                if rid in p2 and int(p1[rid]["employees"]) != int(p2[rid]["employees"])
            ),
            key=lambda x: x["record_id"],
        )
        new = sorted(
            ({"record_id": rid, "company_name": p2[rid]["company_name"]} for rid in p2 if rid not in p1 and p2[rid]["company_name"] not in p1_names),
            key=lambda x: x["record_id"],
        )
        absent = sorted(
            ({"record_id": rid, "company_name": p1[rid]["company_name"]} for rid in p1 if rid not in p2),
            key=lambda x: x["record_id"],
        )
        unmatched = sorted(
            (rid for rid in p2 if rid not in p1 and p2[rid]["company_name"] in p1_names),
        )

        expected = support.load_json(EXPECTED)
        self.assertEqual(changed, expected["changed_employee_counts"])
        self.assertEqual(new, expected["new_companies"])
        self.assertEqual(absent, expected["absent_companies"])
        self.assertEqual([u["record_id"] for u in expected["unmatched_name_collisions"]], unmatched)
        # The one collision maps HL-008's reused name back to HL-001.
        collision = expected["unmatched_name_collisions"][0]
        self.assertEqual(collision["record_id"], "HL-008")
        self.assertEqual(collision["matches_existing_record_id"], name_to_p1["Tidewater Robotics"])
        self.assertFalse(expected["cost_of_support_present"])


class CompareCommandTests(unittest.TestCase):
    def test_company_new_absent_and_unmatched_name_collision(self):
        expected = support.load_json(EXPECTED)
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            support.run("init", project_root=project)
            _, comparison = _compare_period_two(project)

        company = comparison["data_types"]["company"]
        self.assertEqual([r["identity"] for r in company["new"]], ["HL-007"])
        self.assertEqual([r["identity"] for r in company["absent"]], ["HL-006"])
        self.assertEqual([r["identity"] for r in company["unmatched"]], ["HL-008"])

        collision = company["unmatched"][0]
        self.assertEqual(collision["matches_existing_identity"], "HL-001")
        self.assertEqual(collision["resolution"], "unmatched")
        self.assertIn("never authorises a merge", collision["reason"])

        # The fixture's expected collision target agrees with the command's.
        self.assertEqual(
            collision["matches_existing_identity"],
            expected["unmatched_name_collisions"][0]["matches_existing_record_id"],
        )

    def test_company_update_three_changed_employee_counts(self):
        expected = support.load_json(EXPECTED)
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            support.run("init", project_root=project)
            _, comparison = _compare_period_two(project)

        updates = comparison["data_types"]["company_update"]
        ftes_changed = {
            c["identity"]: c
            for c in updates["changed"]
            if any(ch["field"] == "current_ftes" for ch in c["changes"])
        }
        self.assertEqual(set(ftes_changed), {"HL-001", "HL-003", "HL-004"})
        for exp in expected["changed_employee_counts"]:
            change = next(ch for ch in ftes_changed[exp["record_id"]]["changes"] if ch["field"] == "current_ftes")
            self.assertEqual(change["from"], exp["from_employees"])
            self.assertEqual(change["to"], exp["to_employees"])

    def test_cost_of_support_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            support.run("init", project_root=project)
            _, comparison = _compare_period_two(project)
        self.assertFalse(comparison["cost_of_support_present"])

    def test_baseline_written_for_compared_period(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            support.run("init", project_root=project)
            _compare_period_two(project)
            self.assertTrue(compare.baseline_path(project, PERIOD_1).exists())
            self.assertTrue(compare.baseline_path(project, PERIOD_2).exists())


class IdentityOnlyMatchingTests(unittest.TestCase):
    """Direct engine tests: identity is the only key; a name match never merges."""

    def _doc(self, period, rows):
        return {"period": period, "records": {"company": rows}}

    def _row(self, identity, legal_name):
        return {"identity": identity, "fields": {"source_id": identity, "legal_name": legal_name}, "provenance": {}, "flags": []}

    def test_renamed_company_same_id_is_changed_not_new(self):
        prior = compare.build_baseline(self._doc("p1", [self._row("HL-100", "Old Name Inc")]))
        current = self._doc("p2", [self._row("HL-100", "New Name Inc")])
        comparison = compare.compute(current, prior)
        company = comparison["data_types"]["company"]
        self.assertEqual([c["identity"] for c in company["changed"]], ["HL-100"])
        self.assertEqual(company["new"], [])
        self.assertEqual(company["unmatched"], [])
        change = next(ch for ch in company["changed"][0]["changes"] if ch["field"] == "legal_name")
        self.assertEqual(change["from"], "Old Name Inc")
        self.assertEqual(change["to"], "New Name Inc")

    def test_same_name_new_id_is_unmatched_not_merged(self):
        prior = compare.build_baseline(self._doc("p1", [self._row("HL-100", "Acme Robotics")]))
        current = self._doc("p2", [self._row("HL-200", "Acme Robotics")])
        comparison = compare.compute(current, prior)
        company = comparison["data_types"]["company"]
        self.assertEqual([c["identity"] for c in company["unmatched"]], ["HL-200"])
        self.assertEqual(company["unmatched"][0]["matches_existing_identity"], "HL-100")
        # HL-100 is now absent; it is NOT merged into HL-200.
        self.assertEqual([c["identity"] for c in company["absent"]], ["HL-100"])
        self.assertEqual(company["new"], [])

    def test_first_period_reports_everything_new(self):
        current = self._doc("p1", [self._row("HL-100", "Acme"), self._row("HL-101", "Beta")])
        comparison = compare.compute(current, None)
        company = comparison["data_types"]["company"]
        self.assertEqual({c["identity"] for c in company["new"]}, {"HL-100", "HL-101"})
        self.assertEqual(company["changed"], [])
        self.assertEqual(company["absent"], [])
        self.assertIsNone(comparison["baseline_period"])


if __name__ == "__main__":
    unittest.main()
