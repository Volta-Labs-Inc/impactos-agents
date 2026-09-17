"""Schema-vs-contract parity for the store.

Proves the applied store schema matches `contract/data-contract.json`: every data
type maps to a table, every field maps to a column of the expected type, required
fields are NOT NULL, money fields are an (amount numeric, currency char(3)) pair,
and demographic columns live only in person_demographics (never in person and
never in a view) — the classification-placement half of D-18.

Proof needs the schema applied to a real database, so this test creates a fresh,
isolated database inside a running Supabase Postgres cluster, applies the harness
bootstrap and the store migrations (no seeds), introspects information_schema, and
drops the database. It is SKIPPED when no cluster is available, so `make check`
stays green in environments without Docker; run it for real with a running
`supabase start` (or set IMPACTOS_STORE_DB_CONTAINER).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT = REPO_ROOT / "contract" / "data-contract.json"
BOOTSTRAP = REPO_ROOT / "store" / "tests" / "harness" / "local_auth_bootstrap.sql"
MIGRATIONS = REPO_ROOT / "store" / "migrations"

DB_NAME = "impactos_parity_test"
DB_USER = os.environ.get("IMPACTOS_STORE_DB_USER", "postgres")

# contract type name -> table name (only where they differ)
TABLE_NAME = {"organisation": "organization"}

# information_schema.data_type expected for each contract field type
TYPE_MAP = {
    "string": "text",
    "text": "text",
    "email": "text",
    "phone": "text",
    "url": "text",
    "single_select": "text",
    "multi_select": "ARRAY",
    "year": "integer",
    "integer": "integer",
    "number": "numeric",
    "boolean": "boolean",
    "date": "date",
    "ref": "uuid",
}


def _discover_container() -> str:
    env = os.environ.get("IMPACTOS_STORE_DB_CONTAINER")
    if env:
        return env
    if not shutil.which("docker"):
        return ""
    try:
        names = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture_output=True, text=True, check=True,
        ).stdout.split()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""
    dbs = [n for n in names if n.startswith("supabase_db_")]
    return dbs[0] if len(dbs) == 1 else ""


def _psql(container: str, db: str, sql: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["docker", "exec", "-i", container, "psql", "-U", DB_USER, "-d", db,
         "-v", "ON_ERROR_STOP=1", "-At", "-F", "|", "-c", sql],
        capture_output=True, text=True,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(f"psql failed: {proc.stderr.strip()}")
    return proc.stdout


def _psql_file(container: str, db: str, path: Path) -> None:
    with open(path, "rb") as handle:
        proc = subprocess.run(
            ["docker", "exec", "-i", container, "psql", "-U", DB_USER, "-d", db,
             "-v", "ON_ERROR_STOP=1", "-q"],
            stdin=handle, capture_output=True, text=True,
        )
    if proc.returncode != 0:
        raise RuntimeError(f"applying {path.name} failed: {proc.stderr.strip()}")


class ContractParityTest(unittest.TestCase):
    container = ""
    columns: dict = {}
    views: set = set()

    @classmethod
    def setUpClass(cls):
        cls.container = _discover_container()
        if not cls.container:
            raise unittest.SkipTest(
                "no Supabase Postgres cluster available "
                "(set IMPACTOS_STORE_DB_CONTAINER or run `supabase start`)"
            )
        # Reachability check.
        probe = subprocess.run(
            ["docker", "exec", "-i", cls.container, "psql", "-U", DB_USER,
             "-d", "postgres", "-tAc", "select 1"],
            capture_output=True, text=True,
        )
        if probe.returncode != 0:
            raise unittest.SkipTest(f"cluster '{cls.container}' not reachable")

        subprocess.run(["docker", "exec", "-i", cls.container, "dropdb", "-U",
                        DB_USER, "--if-exists", DB_NAME], capture_output=True, text=True)
        subprocess.run(["docker", "exec", "-i", cls.container, "createdb", "-U",
                        DB_USER, DB_NAME], capture_output=True, text=True, check=True)
        _psql_file(cls.container, DB_NAME, BOOTSTRAP)
        for migration in sorted(MIGRATIONS.glob("*.sql")):
            _psql_file(cls.container, DB_NAME, migration)

        cls.columns = {}
        rows = _psql(
            cls.container, DB_NAME,
            "select table_name, column_name, data_type, is_nullable "
            "from information_schema.columns where table_schema='public'",
        )
        for line in rows.splitlines():
            if not line:
                continue
            table, column, data_type, nullable = line.split("|")
            cls.columns.setdefault(table, {})[column] = (data_type, nullable == "YES")

    @classmethod
    def tearDownClass(cls):
        if cls.container:
            subprocess.run(["docker", "exec", "-i", cls.container, "dropdb", "-U",
                            DB_USER, "--if-exists", DB_NAME], capture_output=True, text=True)

    def _contract(self):
        return json.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_every_data_type_has_a_table(self):
        for type_name in self._contract()["data_types"]:
            table = TABLE_NAME.get(type_name, type_name)
            self.assertIn(table, self.columns, f"missing table for data type {type_name!r}")

    def test_fields_map_to_columns_of_the_expected_type(self):
        contract = self._contract()
        for type_name, spec in contract["data_types"].items():
            table = TABLE_NAME.get(type_name, type_name)
            cols = self.columns.get(table, {})
            for field, fspec in spec["fields"].items():
                ftype = fspec["type"]
                required = bool(fspec.get("required"))
                classification = fspec.get("classification")

                # Demographic columns live in person_demographics, never here.
                if classification == "demographic":
                    self.assertNotIn(
                        field, cols,
                        f"{table}.{field} is demographic and must not live on {table}")
                    dcols = self.columns.get("person_demographics", {})
                    self.assertIn("demographics", dcols,
                                  "person_demographics must hold the demographics column")
                    self.assertEqual(dcols["demographics"][0], "ARRAY",
                                     "person_demographics.demographics must be an array")
                    continue

                if ftype == "money":
                    self._assert_money(table, field, cols)
                    continue

                # Only real reference fields become <name>_id columns; a plain
                # string field that happens to end in _ref keeps its name.
                column = field[:-4] + "_id" if ftype == "ref" else field
                self.assertIn(column, cols, f"{table} is missing column {column!r}")
                data_type, nullable = cols[column]
                self.assertEqual(
                    data_type, TYPE_MAP[ftype],
                    f"{table}.{column}: expected {TYPE_MAP[ftype]} for {ftype}, got {data_type}")
                if required:
                    self.assertFalse(nullable, f"{table}.{column} is required and must be NOT NULL")

    def _assert_money(self, table, field, cols):
        self.assertIn(field, cols, f"{table} is missing money amount column {field!r}")
        self.assertEqual(cols[field][0], "numeric",
                         f"{table}.{field} money amount must be numeric")
        currency = f"{field}_currency"
        self.assertIn(currency, cols, f"{table} is missing money currency column {currency!r}")
        self.assertEqual(cols[currency][0], "character",
                         f"{table}.{currency} must be char(3)")

    def test_source_identity_columns_are_not_null(self):
        contract = self._contract()
        for type_name in contract["data_types"]:
            table = TABLE_NAME.get(type_name, type_name)
            cols = self.columns.get(table, {})
            for identity in ("source_system", "source_id"):
                self.assertIn(identity, cols, f"{table} missing {identity}")
                self.assertFalse(cols[identity][1], f"{table}.{identity} must be NOT NULL")

    def test_demographics_not_exposed_by_any_view(self):
        usage = _psql(
            self.container, DB_NAME,
            "select count(*) from information_schema.view_column_usage "
            "where view_schema='public' and table_name='person_demographics'",
        ).strip()
        self.assertEqual(usage, "0", "no public view may read person_demographics")


if __name__ == "__main__":
    unittest.main()
