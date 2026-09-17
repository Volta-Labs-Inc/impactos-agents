"""SR-08 / AC-04: a demographic hint in a name or free-text cell is never turned
into a value. With no source column declaring demographics, the person's
demographics stay unset and the row is flagged for a human."""

from __future__ import annotations

import unittest

import impactos_support as support
from impactos_agent import mapping


def _payload_with_hint():
    return {
        "impactos_source": "1.0.0",
        "source_type": "export",
        "vendor": "csv",
        "meta": {"source_file": "contacts.csv", "content_sha256": "0" * 64},
        "sheets": {
            "default": {
                "columns": ["contact_email", "contact_first_name", "contact_last_name"],
                "rows": [
                    {
                        "contact_email": "priya.sharma@example.org",
                        "contact_first_name": "Priya, she/her",
                        "contact_last_name": "Sharma",
                    }
                ],
            }
        },
    }


# A mapping with NO declared_demographics for the person data type.
PERSON_MAPPING = {
    "source": "hint-test",
    "data_types": {
        "person": {
            "sheet": "default",
            "identity": "contact_email",
            "constants": {"source_system": "hint-test"},
            "columns": {
                "contact_first_name": {"field": "first_name", "transform": "copy"},
                "contact_last_name": {"field": "last_name", "transform": "copy"},
                "contact_email": {"field": "email", "transform": "copy"},
            },
        }
    },
}


class NeverInferTests(unittest.TestCase):
    def setUp(self):
        self.document = mapping.apply_mapping(
            _payload_with_hint(), PERSON_MAPPING, support.PERIOD, confirmed=True
        )
        self.person = self.document["records"]["person"][0]

    def test_demographics_are_not_set(self):
        self.assertNotIn("demographics", self.person["fields"])

    def test_row_is_flagged_never_inferred(self):
        self.assertIn("never_inferred_demographic", self.person["flags"])
        flag_kinds = {f.get("flag") for f in self.document["flags"]}
        self.assertIn("never_inferred_demographic", flag_kinds)

    def test_declared_demographics_do_map(self):
        # Control: with a declared demographic column an explicit Yes IS mapped,
        # proving the never-infer rule is about undeclared hints, not all demographics.
        payload = {
            "impactos_source": "1.0.0",
            "source_type": "export",
            "vendor": "csv",
            "meta": {"source_file": "c.csv", "content_sha256": "0" * 64},
            "sheets": {
                "default": {
                    "columns": ["contact_email", "dg_women"],
                    "rows": [{"contact_email": "a@example.org", "dg_women": "Yes"}],
                }
            },
        }
        declared = {
            "source": "declared",
            "data_types": {
                "person": {
                    "sheet": "default",
                    "identity": "contact_email",
                    "constants": {"source_system": "declared"},
                    "columns": {"contact_email": {"field": "email", "transform": "copy"}},
                    "declared_demographics": {"dg_women": "Women"},
                }
            },
        }
        document = mapping.apply_mapping(payload, declared, support.PERIOD, confirmed=True)
        person = document["records"]["person"][0]
        self.assertEqual(person["fields"]["demographics"], ["Women"])


if __name__ == "__main__":
    unittest.main()
