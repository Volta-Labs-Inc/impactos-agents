"""SR-11: every exported workbook cell traces to a provenance entry naming a
source file and sha256 (or a derivation with contributors), a sheet/column, a row
identity and the period's exported-at."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import impactos_support as support


class ProvenanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.project = Path(cls._tmp.name)
        support.build_records(cls.project)
        support.export(cls.project)
        cls.report = support.report_dir(cls.project)
        cls.manifest = support.load_json(cls.report / "provenance.json")
        cls.cells = support.workbook_data_cells(cls.report / "bai-v5.xlsx")

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_every_workbook_cell_has_a_manifest_entry(self):
        manifest = self.manifest["cells"]
        missing = []
        for sheet, sheet_cells in self.cells.items():
            for ref in sheet_cells:
                key = f"{sheet}!{ref}"
                if key not in manifest:
                    missing.append(key)
        self.assertEqual(missing, [], msg=f"cells without provenance: {missing[:10]}")

    def test_manifest_has_no_orphan_entries(self):
        produced = {f"{sheet}!{ref}" for sheet, cells in self.cells.items() for ref in cells}
        orphans = [k for k in self.manifest["cells"] if k not in produced]
        self.assertEqual(orphans, [], msg=f"provenance entries with no cell: {orphans[:10]}")

    def test_cell_count_matches(self):
        produced = sum(len(cells) for cells in self.cells.values())
        self.assertEqual(self.manifest["cell_count"], produced)

    def test_every_entry_is_fully_traceable(self):
        for key, entry in self.manifest["cells"].items():
            self.assertEqual(entry["exported_at"], support.PERIOD, msg=key)
            if "derivation" in entry:
                self.assertTrue(entry["contributors"], msg=f"{key} derivation has no contributors")
                for contributor in entry["contributors"]:
                    self.assertIn("source_file", contributor)
                    self.assertIn("sha256", contributor)
                    self.assertIn("row_identity", contributor)
            elif entry.get("origin") == "mapping_constant":
                # A value the mapping author declared (e.g. the update date): it is
                # traceable to the mapping file, not a source cell.
                self.assertIn("mapping", entry, msg=key)
                self.assertIn("value", entry, msg=key)
                self.assertIn("row_identity", entry, msg=key)
            else:
                for field in ("source_file", "sha256", "sheet", "column", "row_identity"):
                    self.assertIn(field, entry, msg=f"{key} missing {field}")
                self.assertEqual(len(entry["sha256"]), 64, msg=key)

    def test_exported_at_comes_from_the_period(self):
        self.assertEqual(self.manifest["exported_at"], support.PERIOD)


if __name__ == "__main__":
    unittest.main()
