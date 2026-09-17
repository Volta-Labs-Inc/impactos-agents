"""Validate every contract file against its JSON Schema (Draft 2020-12).

The only non-standard-library dependency is ``jsonschema``. Run standalone or
via ``make check``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DIR = REPO_ROOT / "contract"
SCHEMA_DIR = CONTRACT_DIR / "schema"

PAIRS = [
    ("data-contract.json", "data-contract.schema.json"),
    ("tracks.json", "tracks.schema.json"),
    ("reporting-profile.json", "reporting-profile.schema.json"),
    ("acceptance-rules.json", "acceptance-rules.schema.json"),
    ("exports/bai-template-v5.json", "bai-template-v5.schema.json"),
    ("release-manifest.json", "release-manifest.schema.json"),
]


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    problems = []
    for contract_name, schema_name in PAIRS:
        contract_path = CONTRACT_DIR / contract_name
        schema = _load(SCHEMA_DIR / schema_name)
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        instance = _load(contract_path)
        errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
        if errors:
            for err in errors:
                problems.append(f"{contract_name} {list(err.path)}: {err.message}")
        else:
            print(f"  ok  {contract_name}")

    if problems:
        print("JSON Schema validation FAILED:")
        for line in problems:
            print(f"  - {line}")
        return 1
    print("JSON Schema validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
