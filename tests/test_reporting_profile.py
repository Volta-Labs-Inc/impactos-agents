"""The reporting profile anchors every field to a public framework and maps it
to a place the data contract can populate."""

from __future__ import annotations

import unittest

import support


class ReportingProfileTests(unittest.TestCase):
    def setUp(self):
        self.profile = support.load_reporting_profile()
        self.contract = support.load_contract()

    def test_every_field_anchor_is_declared(self):
        declared = set(self.profile["anchors"])
        for field in self.profile["fields"]:
            self.assertIn(
                field["anchor"],
                declared,
                msg=f"{field['key']} anchor {field['anchor']!r} not in anchors list",
            )

    def test_contract_paths_resolve_to_the_data_contract(self):
        types = self.contract["data_types"]
        for field in self.profile["fields"]:
            path = field["contract_path"]
            if path.startswith("derived:"):
                # a derived value must still cite at least one real data type
                self.assertTrue(field.get("derivation"), msg=f"{field['key']} lacks derivation")
                continue
            self.assertIn(".", path, msg=f"{field['key']} path {path!r}")
            type_name, field_name = path.split(".", 1)
            self.assertIn(type_name, types, msg=f"{field['key']} -> {type_name}")
            self.assertIn(
                field_name,
                types[type_name]["fields"],
                msg=f"{field['key']} -> {path}",
            )

    def test_keys_are_unique(self):
        keys = [f["key"] for f in self.profile["fields"]]
        self.assertEqual(len(keys), len(set(keys)))


if __name__ == "__main__":
    unittest.main()
