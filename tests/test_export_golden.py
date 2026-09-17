"""SR-09: a full export reproduces the committed golden profile, gaps, provenance
and workbook cells, the workbook is a valid BAI v5 template, and every profile
field is either populated or listed as a gap (their union is the whole profile)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import impactos_support as support
from impactos_agent import contract, xlsx


class ExportGoldenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.project = Path(cls._tmp.name)
        support.build_records(cls.project)
        cls.result = support.export(cls.project)
        cls.report = support.report_dir(cls.project)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_export_passes(self):
        self.assertEqual(self.result.exit_code, 0, msg=self.result.errors)
        self.assertEqual(self.result.data["template_problems"], [])

    def test_profile_matches_golden(self):
        self.assertEqual(
            support.load_json(self.report / "profile.json"),
            support.load_json(support.GOLDEN / "profile.json"),
        )

    def test_provenance_matches_golden(self):
        self.assertEqual(
            support.load_json(self.report / "provenance.json"),
            support.load_json(support.GOLDEN / "provenance.json"),
        )

    def test_gaps_md_matches_golden(self):
        self.assertEqual(
            (self.report / "gaps.md").read_text(encoding="utf-8"),
            (support.GOLDEN / "gaps.md").read_text(encoding="utf-8"),
        )

    def test_workbook_cells_match_golden(self):
        produced = support.workbook_data_cells(self.report / "bai-v5.xlsx")
        golden = support.load_json(support.GOLDEN / "workbook-cells.json")
        self.assertEqual(produced, golden)

    def test_output_is_valid_bai_v5_template(self):
        problems = xlsx.validate_bai_template(
            self.report / "bai-v5.xlsx", contract.bai_export_contract()
        )
        self.assertEqual(problems, [])

    def test_every_profile_field_is_populated_or_a_gap(self):
        profile = support.load_json(self.report / "profile.json")
        all_keys = {f["key"] for f in profile["fields"]}
        populated = set(profile["populated"])
        gaps = set(profile["gaps"])
        self.assertEqual(populated | gaps, all_keys)
        self.assertEqual(populated & gaps, set())
        spec_keys = {f["key"] for f in contract.reporting_profile()["fields"]}
        self.assertEqual(all_keys, spec_keys)

    def test_every_gap_has_a_reason(self):
        profile = support.load_json(self.report / "profile.json")
        for entry in profile["fields"]:
            if entry["status"] == "gap":
                self.assertTrue(entry.get("reason"), msg=f"{entry['key']} gap has no reason")

    def test_demographics_flow_from_declared_columns(self):
        # Period 2 declares demographic columns; the rollup must reach the workbook.
        cells = support.workbook_data_cells(self.report / "bai-v5.xlsx")
        companies = cells["Companies"]
        # HL-001 (row 2) reported dg_women=Yes -> Women column (V) = Yes.
        self.assertEqual(companies.get("V2"), "Yes")

    def test_cost_of_support_is_blank(self):
        cells = support.workbook_data_cells(self.report / "bai-v5.xlsx")
        # Cost of Support (CAD) is column O on Company Updates; never populated.
        for ref in cells.get("Company Updates", {}):
            self.assertFalse(ref.startswith("O"), msg="Cost of Support must stay blank")


if __name__ == "__main__":
    unittest.main()
