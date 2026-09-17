"""SR-16: the anchors guidance document names each framework, supports each
profile field's anchor, and states it is one iteration / a starting point."""

from __future__ import annotations

import unittest

import support


class AnchorsDocTests(unittest.TestCase):
    def setUp(self):
        self.doc_path = support.DOCS_DIR / "reporting-anchors.md"
        self.text = self.doc_path.read_text(encoding="utf-8")
        self.profile = support.load_reporting_profile()

    def test_document_exists_and_is_not_empty(self):
        self.assertTrue(self.text.strip())

    def test_every_profile_anchor_appears_in_the_document(self):
        for anchor in self.profile["anchors"]:
            self.assertIn(
                anchor,
                self.text,
                msg=f"anchor {anchor!r} is not named in reporting-anchors.md",
            )

    def test_every_field_anchor_appears_in_the_document(self):
        for field in self.profile["fields"]:
            self.assertIn(field["anchor"], self.text)

    def test_names_the_frameworks(self):
        for token in ["ISED", "CED", "PacifiCan", "BAI"]:
            self.assertIn(token, self.text)

    def test_states_it_is_a_starting_point(self):
        lowered = self.text.lower()
        self.assertIn("one iteration", lowered)
        self.assertIn("starting point", lowered)

    def test_contains_no_agreement_text(self):
        for marker in ["Contribution Agreement", "Ultimate Recipient", "Schedule A"]:
            self.assertNotIn(marker, self.text)


if __name__ == "__main__":
    unittest.main()
