"""The Harbourline fixture is synthetic, carries no personal information, and the
committed period-2-vs-1 deltas match what the CSVs actually contain."""

from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path

import support
import pii_scan


HARBOURLINE = support.FIXTURES_DIR / "harbourline"
P1_CSV = HARBOURLINE / "crm" / "period-2026-03-31" / "companies.csv"
P2_CSV = HARBOURLINE / "crm" / "period-2026-06-30" / "companies.csv"


def _read_csv(path: Path):
    # utf-8-sig transparently strips a UTF-8 BOM
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


class FixturePiiTests(unittest.TestCase):
    def test_every_email_is_on_example_org(self):
        emails = pii_scan.find_emails(HARBOURLINE)
        self.assertTrue(emails, "expected the fixture to contain email addresses")
        bad = pii_scan.bad_emails(HARBOURLINE)
        self.assertEqual(bad, [], msg=f"non-example.org emails: {bad}")

    def test_no_pii_patterns(self):
        findings = pii_scan.find_pii(HARBOURLINE)
        self.assertEqual(findings, [], msg=f"possible PII: {findings}")

    def test_no_agreement_markers_in_repo(self):
        roots = [support.CONTRACT_DIR, support.DOCS_DIR, support.FIXTURES_DIR]
        findings = pii_scan.find_agreement_markers(roots)
        self.assertEqual(findings, [], msg=f"agreement markers: {findings}")


class FixtureShapeTests(unittest.TestCase):
    def test_period1_csv_has_utf8_bom(self):
        self.assertTrue(P1_CSV.read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_period2_csv_has_utf8_bom(self):
        self.assertTrue(P2_CSV.read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_record_id_is_present_and_stable(self):
        for path in (P1_CSV, P2_CSV):
            rows = _read_csv(path)
            self.assertTrue(all(r.get("record_id") for r in rows))
            ids = [r["record_id"] for r in rows]
            self.assertEqual(len(ids), len(set(ids)), msg=f"duplicate record_id in {path}")

    def test_transcripts_cover_three_notetaker_formats(self):
        tdir = HARBOURLINE / "transcripts"
        names = "\n".join(p.name for p in tdir.iterdir())
        self.assertIn("fireflies", names)
        self.assertIn("granola", names)
        self.assertIn("fathom", names)


class CompareDeltaTests(unittest.TestCase):
    def setUp(self):
        self.compare = json.loads((HARBOURLINE / "expected" / "compare.json").read_text(encoding="utf-8"))
        self.p1 = {r["record_id"]: r for r in _read_csv(P1_CSV)}
        self.p2 = {r["record_id"]: r for r in _read_csv(P2_CSV)}

    def test_committed_delta_counts(self):
        self.assertEqual(len(self.compare["changed_employee_counts"]), 3)
        self.assertEqual(len(self.compare["new_companies"]), 1)
        self.assertEqual(len(self.compare["absent_companies"]), 1)
        self.assertEqual(len(self.compare["unmatched_name_collisions"]), 1)
        self.assertTrue(self.compare["demographic_columns_added"])
        self.assertFalse(self.compare["cost_of_support_present"])

    def test_changed_employee_counts_match_the_csvs(self):
        for entry in self.compare["changed_employee_counts"]:
            rid = entry["record_id"]
            self.assertIn(rid, self.p1)
            self.assertIn(rid, self.p2)
            self.assertEqual(int(self.p1[rid]["employees"]), entry["from_employees"])
            self.assertEqual(int(self.p2[rid]["employees"]), entry["to_employees"])
            self.assertNotEqual(entry["from_employees"], entry["to_employees"])
        # no other company silently changed
        actually_changed = {
            rid for rid in self.p1
            if rid in self.p2 and int(self.p1[rid]["employees"]) != int(self.p2[rid]["employees"])
        }
        self.assertEqual(
            actually_changed,
            {e["record_id"] for e in self.compare["changed_employee_counts"]},
        )

    def test_new_company_is_new_id_and_new_name(self):
        self.assertEqual(len(self.compare["new_companies"]), 1)
        entry = self.compare["new_companies"][0]
        rid = entry["record_id"]
        self.assertNotIn(rid, self.p1)
        p1_names = {r["company_name"] for r in self.p1.values()}
        self.assertNotIn(entry["company_name"], p1_names)

    def test_absent_company_is_in_period1_only(self):
        entry = self.compare["absent_companies"][0]
        self.assertIn(entry["record_id"], self.p1)
        self.assertNotIn(entry["record_id"], self.p2)

    def test_name_collision_is_unmatched_never_merged(self):
        entry = self.compare["unmatched_name_collisions"][0]
        rid = entry["record_id"]
        self.assertNotIn(rid, self.p1, "the colliding row has a genuinely new identifier")
        # its name matches an existing company
        p1_names = {r["company_name"]: r["record_id"] for r in self.p1.values()}
        self.assertIn(entry["company_name"], p1_names)
        self.assertEqual(entry["matches_existing_record_id"], p1_names[entry["company_name"]])
        self.assertEqual(entry["resolution"], "unmatched")

    def test_demographic_columns_added_in_period2_only(self):
        p1_cols = set(_read_csv(P1_CSV)[0].keys())
        p2_cols = set(_read_csv(P2_CSV)[0].keys())
        for col in self.compare["demographic_columns_added"]:
            self.assertIn(col, p2_cols)
            self.assertNotIn(col, p1_cols)

    def test_no_cost_of_support_column_in_crm(self):
        for path in (P1_CSV, P2_CSV):
            cols = [c.lower() for c in _read_csv(path)[0].keys()]
            for col in cols:
                self.assertNotIn("cost of support", col)
                self.assertNotIn("cost_of_support", col)


if __name__ == "__main__":
    unittest.main()
