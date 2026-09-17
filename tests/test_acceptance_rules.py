"""SR-22 (policy half): the acceptance rules the founder queue reads are exactly
the contract's default policy, and the migration seeds them faithfully.

The database enforcement (a founder may auto-accept only, review classes need
staff, another founder's submission is refused, anon cannot execute the function)
is proven by the pgTAP suite. Here we prove the *policy* the function reads: that
metrics auto-accept and funding, demographics and stage are held for review
(D-17), in both the contract and the migration that seeds the table.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT = REPO_ROOT / "contract" / "acceptance-rules.json"
MIGRATION = REPO_ROOT / "store" / "migrations" / "0004_writes_acceptance_and_queue.sql"

AUTO_ACCEPT = {"identifier", "descriptive", "operational", "metric"}
REVIEW = {"financial", "personal", "demographic", "stage"}


def _contract():
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def _migration_rows():
    """Parse the acceptance_rule seed rows from the migration: ('class','route',..."""
    text = MIGRATION.read_text(encoding="utf-8")
    block = re.search(r"insert into public\.acceptance_rule.*?on conflict", text, re.S)
    assert block, "no acceptance_rule seed block in the migration"
    return dict(re.findall(r"\(\s*'([a-z_]+)',\s*'(auto_accept|review|reject)'", block.group(0)))


class ContractPolicyTests(unittest.TestCase):
    def test_metrics_auto_accept_and_the_rest_review(self):
        policy = _contract()["default_policy_by_class"]
        for field_class in AUTO_ACCEPT:
            self.assertEqual(policy[field_class]["route"], "auto_accept", field_class)
        for field_class in REVIEW:
            self.assertEqual(policy[field_class]["route"], "review", field_class)

    def test_every_route_is_a_declared_route(self):
        contract = _contract()
        allowed = set(contract["routes"])
        for field_class, rule in contract["default_policy_by_class"].items():
            self.assertIn(rule["route"], allowed, field_class)


class MigrationSeedTests(unittest.TestCase):
    def test_migration_seed_matches_the_contract_routes(self):
        contract = _contract()["default_policy_by_class"]
        seeded = _migration_rows()
        want = {field_class: rule["route"] for field_class, rule in contract.items()}
        self.assertEqual(seeded, want)

    def test_a_founder_only_auto_accepts(self):
        """The rule the SQL enforces, stated over the seeded routes: a submission
        is founder-acceptable iff every one of its field classes auto-accepts."""
        seeded = _migration_rows()

        def founder_may_accept(classes):
            return all(seeded.get(c) == "auto_accept" for c in classes)

        self.assertTrue(founder_may_accept(["metric"]))
        self.assertTrue(founder_may_accept(["metric", "operational"]))
        self.assertFalse(founder_may_accept(["financial"]))
        self.assertFalse(founder_may_accept(["metric", "demographic"]))
        self.assertFalse(founder_may_accept(["stage"]))


if __name__ == "__main__":
    unittest.main()
