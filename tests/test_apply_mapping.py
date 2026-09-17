"""SR-07: apply-mapping requires --confirmed, requires an identity column per data
type, reuses a mapping when columns are only added (listing them), and refuses
when columns are removed or renamed or identities duplicate."""

from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

import impactos_support as support
from impactos_agent import mapping, parsers

P1_MAPPING = support.REPO_ROOT / "tests" / "data" / "crm-mapping-p1.json"


def _payload(source: Path):
    payload, _ = parsers.parse_export(source)
    return payload


class ConfirmationGateTests(unittest.TestCase):
    def test_refuses_without_confirmed(self):
        payload = _payload(support.CRM_P2)
        m = mapping.load_mapping(support.CRM_MAPPING)
        with self.assertRaises(mapping.MappingError) as ctx:
            mapping.apply_mapping(payload, m, support.PERIOD, confirmed=False)
        self.assertIn("--confirmed", str(ctx.exception))

    def test_cli_refuses_without_confirmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            support.parse_source(project, support.CRM_P2)
            result = support.run(
                "apply-mapping",
                source=str(support.payload_path(project, support.CRM_P2)),
                mapping=str(support.CRM_MAPPING),
                period=support.PERIOD,
                confirmed=False,
                out=None,
                project_root=project,
            )
            self.assertEqual(result.exit_code, 1)


class IdentityGateTests(unittest.TestCase):
    def test_refuses_mapping_without_identity(self):
        payload = _payload(support.CRM_P2)
        broken = copy.deepcopy(mapping.load_mapping(support.CRM_MAPPING))
        del broken["data_types"]["company"]["identity"]
        with self.assertRaises(mapping.MappingError) as ctx:
            mapping.apply_mapping(payload, broken, support.PERIOD, confirmed=True)
        self.assertIn("identity", str(ctx.exception))
        self.assertIn("company", str(ctx.exception))


class ColumnDriftTests(unittest.TestCase):
    def test_added_columns_reuse_mapping_and_are_listed(self):
        # The period-1 mapping predates the demographic columns; applying it to the
        # period-2 export must still succeed and list the added columns.
        payload = _payload(support.CRM_P2)
        m = mapping.load_mapping(P1_MAPPING)
        document = mapping.apply_mapping(payload, m, support.PERIOD, confirmed=True)
        added = document["additions"]
        self.assertTrue(added, "expected the new demographic columns to be listed")
        for col in ("dg_women", "dg_indigenous", "dg_official_language_minority"):
            self.assertTrue(any(a.endswith(col) for a in added), msg=f"{col} not listed in {added}")
        # The mapping still applied to the columns it knows.
        self.assertEqual(len(document["records"]["company"]), 7)

    def test_cli_added_columns_return_warnings_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            support.parse_source(project, support.CRM_P2)
            result = support.run(
                "apply-mapping",
                source=str(support.payload_path(project, support.CRM_P2)),
                mapping=str(P1_MAPPING),
                period=support.PERIOD,
                confirmed=True,
                out=None,
                project_root=project,
            )
            self.assertEqual(result.exit_code, 2)
            self.assertTrue(result.data["additions"])

    def test_removed_columns_refuse(self):
        # The period-2 mapping references demographic columns absent from period 1.
        payload = _payload(support.CRM_P1)
        m = mapping.load_mapping(support.CRM_MAPPING)
        with self.assertRaises(mapping.MappingError) as ctx:
            mapping.apply_mapping(payload, m, support.PERIOD, confirmed=True)
        message = str(ctx.exception)
        self.assertIn("removed or renamed", message)
        self.assertIn("dg_women", message)

    def test_renamed_column_refuses_and_names_it(self):
        payload = _payload(support.CRM_P2)
        renamed = copy.deepcopy(mapping.load_mapping(support.CRM_MAPPING))
        # Simulate the source header 'company_name' having been renamed: the mapping
        # still points at the old name, which is now absent.
        renamed["data_types"]["company"]["columns"]["company_naam"] = (
            renamed["data_types"]["company"]["columns"].pop("company_name")
        )
        with self.assertRaises(mapping.MappingError) as ctx:
            mapping.apply_mapping(payload, renamed, support.PERIOD, confirmed=True)
        self.assertIn("company_naam", str(ctx.exception))


class DuplicateIdentityTests(unittest.TestCase):
    def test_duplicate_identity_in_one_export_refuses(self):
        payload = {
            "impactos_source": "1.0.0",
            "source_type": "export",
            "vendor": "csv",
            "meta": {"source_file": "dup.csv", "content_sha256": "0" * 64},
            "sheets": {
                "default": {
                    "columns": ["record_id", "company_name"],
                    "rows": [
                        {"record_id": "HL-1", "company_name": "Acme"},
                        {"record_id": "HL-1", "company_name": "Acme Duplicate"},
                    ],
                }
            },
        }
        m = {
            "source": "dup",
            "data_types": {
                "company": {
                    "sheet": "default",
                    "identity": "record_id",
                    "constants": {"source_system": "dup"},
                    "columns": {"company_name": {"field": "legal_name", "transform": "copy"}},
                }
            },
        }
        with self.assertRaises(mapping.MappingError) as ctx:
            mapping.apply_mapping(payload, m, support.PERIOD, confirmed=True)
        self.assertIn("duplicate identity", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
