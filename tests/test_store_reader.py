"""SR-20 / export parity / brief-from-store: the store reader rebuilds the
file-route record shape, drops retracted facts, and the export and brief built
from the store equal the file route for the same records and exclude retracted
values.

No live cluster: a fake store dataset is derived from a file-route records
document (ids assigned to every referenced parent), the reader reconstructs the
document from it, and the exporter/brief run over both. Retraction is proven by
naming one fact retracted and checking it vanishes from both outputs.
"""

from __future__ import annotations

import tempfile
import unittest
import uuid
from pathlib import Path

import impactos_support as support
from impactos_agent import brief, exporter, store_reader

PERIOD = "2026-06-30"

# One small file-route records document (the parity source of truth).
FILE_DOC = {
    "period": PERIOD,
    "records": {
        "company": [
            {"identity": "ACME-1", "fields": {"source_system": "crm", "source_id": "ACME-1",
                                              "legal_name": "Acme Ltd.", "operating_name": "Acme",
                                              "industry": "Software", "city": "Halifax",
                                              "province": "NS", "country": "Canada",
                                              "company_type": "Startup"}},
            {"identity": "BravoCo", "fields": {"source_system": "crm", "source_id": "BravoCo",
                                               "legal_name": "Bravo Co.", "operating_name": "Bravo",
                                               "industry": "Hardware", "city": "Moncton",
                                               "province": "NB", "country": "Canada"}},
        ],
        "person": [
            {"identity": "P-1", "fields": {"source_system": "crm", "source_id": "P-1",
                                           "first_name": "Ada", "last_name": "Alpha",
                                           "email": "ada@example.org", "phone": "555-0100"}},
        ],
        "company_person": [
            {"identity": "CP-1", "fields": {"source_system": "crm", "source_id": "CP-1",
                                            "company_ref": "ACME-1", "person_ref": "P-1",
                                            "role": "Founder", "is_primary": True}},
        ],
        "company_update": [
            {"identity": "U-1", "fields": {"source_system": "crm", "source_id": "U-1",
                                           "company_ref": "ACME-1", "update_date": PERIOD,
                                           "current_ftes": 7, "lifetime_revenue": 250000}},
            {"identity": "U-2", "fields": {"source_system": "crm", "source_id": "U-2",
                                           "company_ref": "BravoCo", "update_date": PERIOD,
                                           "current_ftes": 3}},
        ],
        "funding_event": [
            {"identity": "F-1", "fields": {"source_system": "crm", "source_id": "F-1",
                                           "company_ref": "ACME-1", "funding_type": "angel",
                                           "amount": 500000}},
        ],
        "milestone_position": [
            {"identity": "M-1", "fields": {"source_system": "crm", "source_id": "M-1",
                                           "company_ref": "ACME-1", "track": "software",
                                           "rung_order": 3, "as_of_date": PERIOD}},
        ],
        "interaction": [
            {"identity": "I-1", "fields": {"source_system": "crm", "source_id": "I-1",
                                           "company_ref": "ACME-1", "interaction_type": "meeting",
                                           "occurred_at": "2026-06-01", "subject": "Q2 review"}},
        ],
    },
}

# The store tables the reader selects from (see store_reader._SELECT).
_PARENTS = {"company", "person", "program", "cohort"}


def _uid(source_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, source_id))


def _fake_store(document, retract=None):
    """Turn a file-route document into a {table: rows} store dataset, assigning a
    uuid to every parent and translating *_ref into *_id. ``retract`` is a list of
    (table, source_id) to add as retraction rows."""
    records = document["records"]
    ids = {}
    for entity in _PARENTS:
        for rec in records.get(entity, []):
            ids[(entity, rec["identity"])] = _uid(f"{entity}:{rec['identity']}")

    store = {table: [] for table in store_reader._SELECT}

    ref_entity = {"company_ref": "company", "person_ref": "person",
                  "program_ref": "program", "cohort_ref": "cohort"}

    for table, rows in records.items():
        for rec in rows:
            fields = dict(rec["fields"])
            row = {}
            row_id = ids.get((table, rec["identity"])) or _uid(f"{table}:{rec['identity']}")
            row["id"] = row_id
            for key, value in fields.items():
                if key in ref_entity:
                    row[key[:-4] + "_id"] = ids[(ref_entity[key], value)]
                else:
                    row[key] = value
            store[table].append(row)

    for table, source_id in (retract or []):
        target = next(r for r in store[table] if r.get("source_id") == source_id)
        store["retraction"].append({"fact_table": table, "fact_id": target["id"]})

    return store


def _get_rows_for(store):
    def get_rows(table, select):
        return store.get(table, [])
    return get_rows


def _cells(document):
    tmp = Path(tempfile.mkdtemp())
    exporter.Exporter(document).build(tmp)
    return (support.workbook_data_cells(tmp / "bai-v5.xlsx"),
            support.load_json(tmp / "profile.json"),
            (tmp / "gaps.md").read_text(encoding="utf-8"))


class StoreReaderTests(unittest.TestCase):
    def test_reader_reconstructs_the_file_route_records(self):
        store = _fake_store(FILE_DOC)
        doc = store_reader.read_records(Path("."), PERIOD, get_rows=_get_rows_for(store))
        companies = {r["identity"] for r in doc["records"]["company"]}
        self.assertEqual(companies, {"ACME-1", "BravoCo"})
        update = next(r for r in doc["records"]["company_update"] if r["identity"] == "U-1")
        self.assertEqual(update["fields"]["company_ref"], "ACME-1")
        self.assertEqual(update["fields"]["lifetime_revenue"], 250000)

    def test_store_export_equals_file_export_for_the_same_records(self):
        store = _fake_store(FILE_DOC)
        store_doc = store_reader.read_records(Path("."), PERIOD, get_rows=_get_rows_for(store))
        file_cells, file_profile, file_gaps = _cells(FILE_DOC)
        store_cells, store_profile, store_gaps = _cells(store_doc)
        self.assertEqual(store_cells, file_cells)
        self.assertEqual(store_profile["populated"], file_profile["populated"])
        self.assertEqual(store_profile["gaps"], file_profile["gaps"])
        self.assertEqual(store_gaps, file_gaps)

    def test_retracted_fact_is_absent_from_the_store_export(self):
        # Retract Acme's funding event: the Total Angel cell must disappear.
        store = _fake_store(FILE_DOC, retract=[("funding_event", "F-1")])
        store_doc = store_reader.read_records(Path("."), PERIOD, get_rows=_get_rows_for(store))
        self.assertEqual(store_doc["records"]["funding_event"], [])
        store_cells, _, _ = _cells(store_doc)
        full_cells, _, _ = _cells(FILE_DOC)
        angel_full = [ref for ref, v in full_cells.get("Company Updates", {}).items() if v == 500000]
        self.assertTrue(angel_full, "the full export should carry the angel total")
        angel_store = [ref for ref, v in store_cells.get("Company Updates", {}).items() if v == 500000]
        self.assertEqual(angel_store, [], "retracted funding must not reach the export")

    def test_retracted_fact_is_absent_from_the_store_brief(self):
        # Retract Acme's interaction: the brief must not list it.
        store = _fake_store(FILE_DOC, retract=[("interaction", "I-1")])
        store_doc = store_reader.read_records(Path("."), PERIOD, get_rows=_get_rows_for(store))
        built = brief.build_company_brief(store_doc, "ACME-1")
        self.assertIn("No interactions recorded.", built["markdown"])
        # Without the retraction the interaction shows.
        full_doc = store_reader.read_records(Path("."), PERIOD,
                                             get_rows=_get_rows_for(_fake_store(FILE_DOC)))
        full_brief = brief.build_company_brief(full_doc, "ACME-1")
        self.assertIn("Q2 review", full_brief["markdown"])


if __name__ == "__main__":
    unittest.main()
