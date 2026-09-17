"""Four milestone tracks, each rung carrying a funder stage."""

from __future__ import annotations

import unittest

import support


EXPECTED_RUNG_COUNTS = {
    "software": 6,
    "hardware": 8,
    "medical_device": 7,
    "biotech_pharma": 6,
}


class TracksTests(unittest.TestCase):
    def setUp(self):
        self.tracks_doc = support.load_tracks()
        self.tracks = {t["slug"]: t for t in self.tracks_doc["tracks"]}

    def test_four_expected_tracks(self):
        self.assertEqual(set(self.tracks.keys()), set(EXPECTED_RUNG_COUNTS.keys()))

    def test_rung_counts_match_estate_analysis(self):
        for slug, count in EXPECTED_RUNG_COUNTS.items():
            self.assertEqual(
                len(self.tracks[slug]["rungs"]),
                count,
                msg=f"{slug} should have {count} rungs",
            )

    def test_every_rung_has_a_funder_stage_in_the_vocabulary(self):
        vocab = set(self.tracks_doc["funder_stage_vocabulary"])
        for slug, track in self.tracks.items():
            for rung in track["rungs"]:
                self.assertIn(
                    rung["funder_stage"],
                    vocab,
                    msg=f"{slug} rung {rung['order']} funder_stage {rung['funder_stage']!r}",
                )

    def test_every_rung_has_evidence_and_signal(self):
        for slug, track in self.tracks.items():
            for rung in track["rungs"]:
                self.assertTrue(rung["evidence_description"].strip())
                self.assertTrue(rung["objective_signal"].strip())

    def test_rung_order_is_sequential(self):
        for slug, track in self.tracks.items():
            orders = [rung["order"] for rung in track["rungs"]]
            self.assertEqual(orders, list(range(1, len(orders) + 1)))


if __name__ == "__main__":
    unittest.main()
