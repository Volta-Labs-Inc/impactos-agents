"""SR-18: preview then confirm; an expired, changed or missing preview is
refused; a replayed confirm writes nothing.

The store is stubbed, so these prove the preview/confirm/replay logic — the half
that does not need a live cluster. The database side (atomic batch, idempotency,
RLS) is proven by the pgTAP suite and the fixture-store target.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import impactos_support  # noqa: F401  (puts cli/ on sys.path)
from impactos_agent import store_writes


RECORDS = {
    "period": "2026-06-30",
    "records": {
        "company": [
            {"identity": "ACME-1", "fields": {"source_system": "crm", "source_id": "ACME-1",
                                              "legal_name": "Acme Ltd."}},
        ],
        "company_update": [
            {"identity": "ACME-1", "fields": {"source_system": "crm", "source_id": "U-1",
                                              "company_ref": "ACME-1", "update_date": "2026-06-30",
                                              "current_ftes": 7,
                                              "annual_revenue": {"amount": 250000, "currency": "CAD"}}},
        ],
        "funding_event": [
            {"identity": "F-1", "fields": {"source_system": "crm", "source_id": "F-1",
                                           "company_ref": "ACME-1", "funding_type": "angel",
                                           "amount": {"amount": 500000, "currency": "CAD"}}},
        ],
    },
}


def _project(records=RECORDS) -> Path:
    root = Path(tempfile.mkdtemp())
    (root / "workspace" / "state" / "2026-06-30").mkdir(parents=True)
    (root / "workspace" / "state" / "2026-06-30" / "records.json").write_text(
        json.dumps(records), encoding="utf-8")
    return root


def _args(**kw) -> SimpleNamespace:
    kw.setdefault("json", False)
    kw.setdefault("records", None)
    kw.setdefault("period", "2026-06-30")
    kw.setdefault("confirm", None)
    kw.setdefault("note", None)
    return SimpleNamespace(**kw)


def _stub_get_rows(table, select):
    # Only the company table is referenced by these records.
    if table == "company":
        return [{"id": "2a2a2a2a-0000-4000-8000-0000000000aa", "source_id": "ACME-1"}]
    return []


class PreviewTests(unittest.TestCase):
    def test_preview_writes_a_hashed_file_and_does_not_apply(self):
        root = _project()
        result = store_writes.write(root, _args())
        self.assertEqual(result.verdict, "pass", result.errors)
        h = result.data["request_hash"]
        preview = root / "workspace" / "state" / "previews" / f"{h}.json"
        self.assertTrue(preview.exists())
        # money was flattened; three facts proposed (update + funding).
        self.assertEqual(result.data["fact_count"], 2)
        self.assertEqual(result.data["facts_by_table"],
                         {"company_update": 1, "funding_event": 1})

    def test_same_inputs_hash_the_same(self):
        root = _project()
        first = store_writes.write(root, _args()).data["request_hash"]
        second = store_writes.write(_project(), _args()).data["request_hash"]
        self.assertEqual(first, second)

    def test_batch_id_is_a_uuid_derived_from_the_hash(self):
        root = _project()
        data = store_writes.write(root, _args()).data
        import uuid
        self.assertEqual(str(uuid.UUID(data["batch_id"])), data["batch_id"])
        self.assertEqual(data["batch_id"], store_writes._batch_uuid(data["request_hash"]))


class ConfirmTests(unittest.TestCase):
    def test_confirm_without_a_preview_is_refused(self):
        root = _project()
        result = store_writes.write(root, _args(confirm="a" * 64))
        self.assertEqual(result.verdict, "fail")
        self.assertIn("no preview", result.errors[0])

    def test_confirm_applies_once_and_replays_as_a_noop(self):
        root = _project()
        h = store_writes.write(root, _args()).data["request_hash"]

        calls = {"n": 0}

        def rpc(fn, body):
            self.assertEqual(fn, "apply_write_batch")
            calls["n"] += 1
            if calls["n"] == 1:
                return 200, json.dumps([{"status": "applied", "batch_id": body["p_batch_id"],
                                         "fact_count": 2}]).encode()
            return 200, json.dumps([{"status": "noop", "batch_id": body["p_batch_id"],
                                     "fact_count": 0}]).encode()

        applied = store_writes.write(root, _args(confirm=h), rpc=rpc, get_rows=_stub_get_rows)
        self.assertEqual(applied.verdict, "pass", applied.errors)
        self.assertFalse(applied.data["replayed_noop"])
        self.assertEqual(applied.data["fact_count"], 2)

        replay = store_writes.write(root, _args(confirm=h), rpc=rpc, get_rows=_stub_get_rows)
        self.assertEqual(replay.verdict, "pass", replay.errors)
        self.assertTrue(replay.data["replayed_noop"])
        self.assertEqual(calls["n"], 2)

    def test_confirm_resolves_company_ref_to_a_database_id(self):
        root = _project()
        h = store_writes.write(root, _args()).data["request_hash"]
        captured = {}

        def rpc(fn, body):
            captured["facts"] = body["p_facts"]
            captured["company"] = body["p_company_id"]
            return 200, json.dumps([{"status": "applied", "fact_count": 2}]).encode()

        store_writes.write(root, _args(confirm=h), rpc=rpc, get_rows=_stub_get_rows)
        for fact in captured["facts"]:
            self.assertNotIn("company_ref", fact["record"])
            self.assertEqual(fact["record"]["company_id"], "2a2a2a2a-0000-4000-8000-0000000000aa")
        # a single company across the batch is passed as p_company_id too.
        self.assertEqual(captured["company"], "2a2a2a2a-0000-4000-8000-0000000000aa")

    def test_confirm_flattens_money_before_the_write(self):
        root = _project()
        h = store_writes.write(root, _args()).data["request_hash"]
        captured = {}

        def rpc(fn, body):
            captured["facts"] = body["p_facts"]
            return 200, json.dumps([{"status": "applied", "fact_count": 2}]).encode()

        store_writes.write(root, _args(confirm=h), rpc=rpc, get_rows=_stub_get_rows)
        funding = next(f for f in captured["facts"] if f["fact_table"] == "funding_event")
        self.assertEqual(funding["record"]["amount"], 500000)
        self.assertEqual(funding["record"]["amount_currency"], "CAD")

    def test_expired_preview_is_refused(self):
        root = _project()
        h = store_writes.write(root, _args()).data["request_hash"]
        # Force the stored preview to be already expired.
        preview_path = root / "workspace" / "state" / "previews" / f"{h}.json"
        preview = json.loads(preview_path.read_text())
        preview["expires_at"] = "2000-01-01T00:00:00+00:00"
        preview_path.write_text(json.dumps(preview), encoding="utf-8")
        result = store_writes.write(root, _args(confirm=h), rpc=lambda *a: (200, b"[]"),
                                    get_rows=_stub_get_rows)
        self.assertEqual(result.verdict, "fail")
        self.assertIn("expired", result.errors[0])

    def test_changed_inputs_are_refused(self):
        root = _project()
        h = store_writes.write(root, _args()).data["request_hash"]
        # Change the records after the preview: the hash no longer matches.
        changed = json.loads(json.dumps(RECORDS))
        changed["records"]["company_update"][0]["fields"]["current_ftes"] = 99
        (root / "workspace" / "state" / "2026-06-30" / "records.json").write_text(
            json.dumps(changed), encoding="utf-8")
        result = store_writes.write(root, _args(confirm=h), rpc=lambda *a: (200, b"[]"),
                                    get_rows=_stub_get_rows)
        self.assertEqual(result.verdict, "fail")
        self.assertIn("changed", result.errors[0])


class RetractAndReviewTests(unittest.TestCase):
    def test_retract_requires_a_uuid_and_reason(self):
        root = _project()
        bad = store_writes.retract(root, _args(fact="nope", fact_table="company_update", reason="x"),
                                   post=lambda *a: (201, b""))
        self.assertEqual(bad.verdict, "fail")

    def test_retract_posts_a_retraction_row(self):
        root = _project()
        captured = {}

        def post(table, row):
            captured["table"] = table
            captured["row"] = row
            return 201, b""

        result = store_writes.retract(
            root, _args(fact="2a2a2a2a-0000-4000-8000-0000000000aa",
                        fact_table="company_update", reason="superseded: 250k -> 25k"),
            post=post)
        self.assertEqual(result.verdict, "pass", result.errors)
        self.assertEqual(captured["table"], "retraction")
        self.assertEqual(captured["row"]["fact_table"], "company_update")
        self.assertEqual(captured["row"]["reason"], "superseded: 250k -> 25k")

    def test_review_accept_calls_the_guarded_function(self):
        root = _project()
        captured = {}

        def rpc(fn, body):
            captured["fn"] = fn
            captured["body"] = body
            return 200, json.dumps({"status": "accepted", "fact_count": 1}).encode()

        result = store_writes.review(
            root, _args(submission="2a2a2a2a-0000-4000-8000-0000000000aa",
                        accept=True, reject=False), rpc=rpc)
        self.assertEqual(result.verdict, "pass", result.errors)
        self.assertEqual(captured["fn"], "accept_submission")
        self.assertEqual(captured["body"]["p_submission_id"], "2a2a2a2a-0000-4000-8000-0000000000aa")

    def test_review_requires_exactly_one_of_accept_or_reject(self):
        root = _project()
        result = store_writes.review(
            root, _args(submission="2a2a2a2a-0000-4000-8000-0000000000aa",
                        accept=True, reject=True))
        self.assertEqual(result.verdict, "fail")


if __name__ == "__main__":
    unittest.main()
