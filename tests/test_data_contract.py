"""Semantic constraints on the data contract: the data types present, money as
an object with a currency, demographics recorded on the person (never the
company) using the PacifiCan list, and a per-field classification."""

from __future__ import annotations

import unittest

import support


class DataContractTests(unittest.TestCase):
    def setUp(self):
        self.contract = support.load_contract()
        self.types = self.contract["data_types"]

    def test_all_expected_data_types_present(self):
        self.assertEqual(
            sorted(self.types.keys()),
            sorted(support.EXPECTED_DATA_TYPES),
        )

    def test_money_value_type_carries_amount_and_currency(self):
        money = self.contract["value_types"]["money"]
        self.assertEqual(set(money["shape"].keys()), {"amount", "currency"})
        self.assertIn("amount", money["required_keys"])
        self.assertIn("currency", money["required_keys"])

    def test_every_money_field_uses_the_money_value_type(self):
        money_fields = []
        for type_name, spec in self.types.items():
            for field_name, field in spec["fields"].items():
                if field["type"] == "money":
                    money_fields.append((type_name, field_name))
                    # money fields carry a value, classified financial or metric
                    self.assertIn(field["classification"], {"financial", "metric"})
        # the contract must actually exercise money somewhere
        self.assertTrue(money_fields, "expected at least one money-typed field")

    def test_company_has_no_demographic_field(self):
        company_fields = self.types["company"]["fields"]
        for field_name, field in company_fields.items():
            self.assertNotEqual(
                field["classification"],
                "demographic",
                msg=f"company.{field_name} is classified demographic",
            )
            self.assertNotIn("demograph", field_name.lower())
            self.assertNotIn("diverse", field_name.lower())

    def test_demographics_recorded_on_person_with_pacifican_list(self):
        person_fields = self.types["person"]["fields"]
        self.assertIn("demographics", person_fields)
        demographics = person_fields["demographics"]
        self.assertEqual(demographics["type"], "multi_select")
        self.assertEqual(demographics["classification"], "demographic")
        self.assertEqual(demographics["vocabulary"], "diverse_groups")
        self.assertEqual(
            self.contract["vocabularies"]["diverse_groups"],
            support.PACIFICAN_DIVERSE_GROUPS,
        )

    def test_every_field_has_a_valid_classification(self):
        allowed = set(self.contract["field_classifications"])
        for type_name, spec in self.types.items():
            for field_name, field in spec["fields"].items():
                self.assertIn(
                    field["classification"],
                    allowed,
                    msg=f"{type_name}.{field_name} has classification {field['classification']!r}",
                )

    def test_personal_and_financial_classes_are_used(self):
        seen = {
            field["classification"]
            for spec in self.types.values()
            for field in spec["fields"].values()
        }
        # the personal/financial split later children rely on must exist
        self.assertIn("personal", seen)
        self.assertIn("financial", seen)

    def test_select_fields_reference_a_defined_vocabulary(self):
        vocabs = set(self.contract["vocabularies"].keys())
        for type_name, spec in self.types.items():
            for field_name, field in spec["fields"].items():
                if field["type"] in {"single_select", "multi_select"}:
                    self.assertIn(
                        field["vocabulary"],
                        vocabs,
                        msg=f"{type_name}.{field_name} -> {field['vocabulary']}",
                    )

    def test_ref_fields_point_at_a_real_data_type(self):
        for type_name, spec in self.types.items():
            for field_name, field in spec["fields"].items():
                if field["type"] == "ref":
                    self.assertIn(
                        field["ref"],
                        self.types,
                        msg=f"{type_name}.{field_name} -> {field['ref']}",
                    )


if __name__ == "__main__":
    unittest.main()
