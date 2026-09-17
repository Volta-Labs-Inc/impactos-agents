"""`parse` normalises the three source types, strips a UTF-8 BOM, and reports
malformed workbooks, missing headers and non-UTF-8 input as data (never crashes)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import impactos_support as support
from impactos_agent import parsers


class ExportParseTests(unittest.TestCase):
    def test_csv_bom_is_stripped_and_hashed(self):
        payload, errors = parsers.parse_export(support.CRM_P2)
        self.assertEqual(errors, [])
        self.assertEqual(payload["vendor"], "csv")
        columns = payload["sheets"]["default"]["columns"]
        # The first column header must be clean 'record_id', not '﻿record_id'.
        self.assertEqual(columns[0], "record_id")
        self.assertFalse(columns[0].startswith("﻿"))
        self.assertEqual(len(payload["sheets"]["default"]["rows"]), 7)
        self.assertEqual(len(payload["meta"]["content_sha256"]), 64)

    def test_non_utf8_csv_is_reported_not_crashed(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "latin1.csv"
            bad.write_bytes(b"record_id,name\nHL-1,Caf\xe9 Noir\n")  # 0xe9 is invalid UTF-8
            payload, errors = parsers.parse_export(bad)
            self.assertTrue(errors)
            self.assertIn("UTF-8", errors[0])
            self.assertEqual(payload["sheets"], {})

    def test_xlsx_export_reads_sheets(self):
        payload, errors = parsers.parse_export(support.PROGRAMS)
        self.assertEqual(errors, [])
        self.assertEqual(payload["vendor"], "xlsx")
        self.assertIn("Programs", payload["sheets"])
        self.assertIn("Cohorts", payload["sheets"])

    def test_malformed_workbook_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "broken.xlsx"
            bad.write_bytes(b"this is not a zip archive")
            payload, errors = parsers.parse_export(bad)
            self.assertTrue(errors)
            self.assertEqual(payload["sheets"], {})


class BaiParseTests(unittest.TestCase):
    def test_bai_workbook_parses_sheets(self):
        payload, errors = parsers.parse_bai(support.BAI_WORKBOOK)
        self.assertEqual(payload["vendor"], "bai_v5")
        self.assertIn("Companies", payload["sheets"])
        self.assertIn("Company Updates", payload["sheets"])
        self.assertEqual(len(payload["meta"]["content_sha256"]), 64)

    def test_missing_headers_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "partial.xlsx"
            from openpyxl import Workbook

            wb = Workbook()
            ws = wb.active
            ws.title = "Companies"
            ws.append(["Company ID", "Business Name"])  # most required columns absent
            ws.append(["HL-1", "Acme"])
            wb.save(path)
            payload, errors = parsers.parse_bai(path)
            self.assertTrue(any("missing columns" in e for e in errors), msg=errors)


class TranscriptParseTests(unittest.TestCase):
    def test_fireflies_json(self):
        source = support.FIXTURE / "transcripts" / "fireflies-tidewater-2026-04-18.json"
        payload, errors = parsers.parse_transcript(source)
        self.assertEqual(errors, [])
        self.assertEqual(payload["vendor"], "fireflies")
        self.assertEqual(payload["transcript"]["source_meeting_id"], "ff-2026-0418-001")
        self.assertEqual(len(payload["transcript"]["segments"]), 3)

    def test_granola_md(self):
        source = support.FIXTURE / "transcripts" / "granola-saltmarsh-2026-05-06.md"
        payload, errors = parsers.parse_transcript(source)
        self.assertEqual(payload["vendor"], "granola")
        self.assertTrue(payload["transcript"]["source_meeting_id"].startswith("granola:"))
        self.assertTrue(payload["transcript"]["participants"])

    def test_fathom_txt(self):
        source = support.FIXTURE / "transcripts" / "fathom-nectar-2026-05-20.txt"
        payload, errors = parsers.parse_transcript(source)
        self.assertEqual(payload["vendor"], "fathom")
        self.assertTrue(payload["transcript"]["segments"])
        # A vendor id and content hash are always present.
        self.assertTrue(payload["transcript"]["source_meeting_id"])
        self.assertEqual(len(payload["meta"]["content_sha256"]), 64)

    def test_unrecognised_transcript_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mystery.txt"
            path.write_text("just some notes with no vendor markers\n", encoding="utf-8")
            payload, errors = parsers.parse_transcript(path)
            self.assertTrue(errors)
            self.assertEqual(payload["vendor"], "unknown")


if __name__ == "__main__":
    unittest.main()
