"""Every data type declares an identity rule, and the schema rejects an identity
that is name-derived or lacks a source identifier."""

from __future__ import annotations

import copy
import unittest

import support


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.contract = support.load_contract()
        self.schema = support.load_schema("data-contract.schema.json")
        self.types = self.contract["data_types"]

    def test_every_data_type_declares_an_identity_rule(self):
        for type_name, spec in self.types.items():
            rule = spec["identity_rule"]
            self.assertTrue(rule["source_identifier_required"])
            self.assertTrue(rule["name_derived_forbidden"])
            self.assertGreaterEqual(len(rule["keys"]), 1)

    def test_identity_keys_reference_real_fields(self):
        for type_name, spec in self.types.items():
            fields = set(spec["fields"].keys())
            for key in spec["identity_rule"]["keys"]:
                self.assertIn(
                    key,
                    fields,
                    msg=f"{type_name} identity key {key!r} is not a field",
                )

    def test_schema_rejects_name_derived_identity(self):
        broken = copy.deepcopy(self.contract)
        broken["data_types"]["company"]["identity_rule"]["name_derived_forbidden"] = False
        self.assertNotEqual(
            support.schema_errors(broken, self.schema),
            [],
            msg="schema must reject name_derived_forbidden = false",
        )

    def test_schema_rejects_missing_source_identifier_requirement(self):
        broken = copy.deepcopy(self.contract)
        broken["data_types"]["company"]["identity_rule"]["source_identifier_required"] = False
        self.assertNotEqual(support.schema_errors(broken, self.schema), [])

    def test_schema_rejects_identity_without_keys(self):
        broken = copy.deepcopy(self.contract)
        broken["data_types"]["company"]["identity_rule"]["keys"] = []
        self.assertNotEqual(support.schema_errors(broken, self.schema), [])


if __name__ == "__main__":
    unittest.main()
