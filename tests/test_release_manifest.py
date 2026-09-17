"""The release manifest's sha256 values match the contract files on disk, and the
contract version is consistent everywhere."""

from __future__ import annotations

import hashlib
import unittest

import support
import release_manifest


class ReleaseManifestTests(unittest.TestCase):
    def setUp(self):
        self.manifest = support.load_release_manifest()

    def test_version_is_consistent(self):
        version = (support.CONTRACT_DIR / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(self.manifest["contract_version"], version)
        for loader in (
            support.load_contract,
            support.load_tracks,
            support.load_reporting_profile,
            support.load_acceptance_rules,
            support.load_bai_export,
        ):
            self.assertEqual(loader()["contract_version"], version)

    def test_every_contract_file_is_listed(self):
        listed = {entry["path"] for entry in self.manifest["files"]}
        self.assertEqual(listed, set(release_manifest.CONTRACT_FILES))

    def test_sha256_matches_disk(self):
        for entry in self.manifest["files"]:
            path = support.CONTRACT_DIR / entry["path"]
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(actual, entry["sha256"], msg=f"sha256 mismatch for {entry['path']}")
            self.assertEqual(path.stat().st_size, entry["bytes"])

    def test_release_check_passes(self):
        self.assertEqual(release_manifest.check(), 0)


if __name__ == "__main__":
    unittest.main()
