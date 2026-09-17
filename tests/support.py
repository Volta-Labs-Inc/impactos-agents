"""Shared helpers for the contract test suite.

The only non-standard-library dependency in this repository is ``jsonschema``,
used here to validate every contract file against its JSON Schema. Everything
else is Python standard library so the suite runs from a clean checkout with
``python3 -m unittest`` (pytest also collects these ``unittest`` cases).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DIR = REPO_ROOT / "contract"
SCHEMA_DIR = CONTRACT_DIR / "schema"
DOCS_DIR = REPO_ROOT / "docs"
FIXTURES_DIR = REPO_ROOT / "fixtures"
TOOLS_DIR = REPO_ROOT / "tools"

sys.path.insert(0, str(TOOLS_DIR))

# The PacifiCan "diverse groups" list (glossary). The person.demographics
# vocabulary must equal this exactly, and it is recorded per person, never per
# company.
PACIFICAN_DIVERSE_GROUPS = [
    "Women",
    "Indigenous",
    "Racialized",
    "Persons with disabilities",
    "2SLGBTQ+",
    "Youth",
    "Immigrants",
    "Official Language Minority Communities",
]

EXPECTED_DATA_TYPES = [
    "organisation",
    "company",
    "person",
    "company_person",
    "program",
    "cohort",
    "membership",
    "interaction",
    "company_update",
    "funding_event",
    "team_member_period",
    "milestone_position",
    "milestone_target",
    "submission",
]


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_schema(name: str):
    return load_json(SCHEMA_DIR / name)


def schema_errors(instance, schema):
    validator = Draft202012Validator(schema)
    return sorted(validator.iter_errors(instance), key=lambda e: list(e.path))


def load_contract():
    return load_json(CONTRACT_DIR / "data-contract.json")


def load_tracks():
    return load_json(CONTRACT_DIR / "tracks.json")


def load_reporting_profile():
    return load_json(CONTRACT_DIR / "reporting-profile.json")


def load_acceptance_rules():
    return load_json(CONTRACT_DIR / "acceptance-rules.json")


def load_bai_export():
    return load_json(CONTRACT_DIR / "exports" / "bai-template-v5.json")


def load_release_manifest():
    return load_json(CONTRACT_DIR / "release-manifest.json")
