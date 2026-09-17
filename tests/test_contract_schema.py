"""Every contract file validates against its JSON Schema, and the money value
type rejects a bare number."""

from __future__ import annotations

import unittest

from jsonschema import Draft202012Validator

import support


CONTRACT_TO_SCHEMA = [
    ("data-contract.json", "data-contract.schema.json"),
    ("tracks.json", "tracks.schema.json"),
    ("reporting-profile.json", "reporting-profile.schema.json"),
    ("acceptance-rules.json", "acceptance-rules.schema.json"),
    ("exports/bai-template-v5.json", "bai-template-v5.schema.json"),
    ("release-manifest.json", "release-manifest.schema.json"),
]


class ContractSchemaTests(unittest.TestCase):
    def test_schema_files_are_valid_json_schema(self):
        for _, schema_name in CONTRACT_TO_SCHEMA + [(None, "money.schema.json")]:
            with self.subTest(schema=schema_name):
                schema = support.load_schema(schema_name)
                Draft202012Validator.check_schema(schema)

    def test_every_contract_validates_against_its_schema(self):
        for contract_name, schema_name in CONTRACT_TO_SCHEMA:
            with self.subTest(contract=contract_name):
                instance = support.load_json(support.CONTRACT_DIR / contract_name)
                schema = support.load_schema(schema_name)
                errors = support.schema_errors(instance, schema)
                self.assertEqual(
                    errors,
                    [],
                    msg="\n".join(f"{list(e.path)}: {e.message}" for e in errors),
                )

    def test_money_schema_rejects_bare_number_and_accepts_object(self):
        money_schema = support.load_schema("money.schema.json")
        self.assertNotEqual(
            support.schema_errors(1500, money_schema),
            [],
            msg="a bare number must not validate as money",
        )
        self.assertNotEqual(support.schema_errors(1500.0, money_schema), [])
        self.assertNotEqual(support.schema_errors("1500", money_schema), [])
        self.assertEqual(
            support.schema_errors({"amount": 1500, "currency": "CAD"}, money_schema),
            [],
        )
        # currency is mandatory: an amount alone is not money
        self.assertNotEqual(support.schema_errors({"amount": 1500}, money_schema), [])


if __name__ == "__main__":
    unittest.main()
