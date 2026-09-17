"""SR-10 (gate): `export --after-compare <hash>` refuses unless an acknowledged,
still-valid compare exists for the period. It refuses when no compare exists, when
a source changed after the compare (the records differ), and when the prior
baseline changed. Re-running compare for the same period is idempotent and never
compares a period to itself.

Plain `export` (no --after-compare) is unchanged: the single-period export flow
from issue #2/#3 still works without a compare.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import impactos_support as support
from impactos_agent import cli, compare

PERIOD_1 = "2026-03-31"
PERIOD_2 = "2026-06-30"
CRM_MAPPING_P1 = support.REPO_ROOT / "tests" / "data" / "crm-mapping-p1.json"


def _run(command_func, **kwargs):
    return command_func(support.ns(**kwargs))


def _establish_baseline(project: Path) -> None:
    support.parse_source(project, support.CRM_P1, PERIOD_1)
    _run(
        cli.cmd_apply_mapping,
        source=str(support.payload_path(project, support.CRM_P1, PERIOD_1)),
        mapping=str(CRM_MAPPING_P1),
        period=PERIOD_1,
        confirmed=True,
        out=None,
        project_root=project,
    )
    _run(cli.cmd_compare, period=PERIOD_1, out=None, project_root=project)


def _compare_hash(project: Path, period: str = PERIOD_2) -> str:
    comparison = support.load_json(project / "workspace" / "reports" / period / "compare.json")
    return comparison["acknowledgement"]["hash"]


class ExportGateTests(unittest.TestCase):
    def test_export_refused_without_compare(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            support.run("init", project_root=project)
            support.build_records(project, PERIOD_2)  # p2 records, no compare
            result = _run(cli.cmd_export, period=PERIOD_2, out=None, after_compare="anything", project_root=project)
            self.assertEqual(result.exit_code, 1)
            self.assertTrue(any("no compare" in e for e in result.errors), msg=result.errors)

    def test_export_succeeds_after_valid_compare(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            support.run("init", project_root=project)
            _establish_baseline(project)
            support.build_records(project, PERIOD_2)
            _run(cli.cmd_compare, period=PERIOD_2, out=None, project_root=project)
            result = _run(
                cli.cmd_export, period=PERIOD_2, out=None,
                after_compare=_compare_hash(project), project_root=project,
            )
            self.assertIn(result.exit_code, (0, 2), msg=result.errors)
            self.assertTrue((project / "workspace" / "reports" / PERIOD_2 / "bai-v5.xlsx").exists())

    def test_export_refused_on_wrong_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            support.run("init", project_root=project)
            _establish_baseline(project)
            support.build_records(project, PERIOD_2)
            _run(cli.cmd_compare, period=PERIOD_2, out=None, project_root=project)
            result = _run(
                cli.cmd_export, period=PERIOD_2, out=None,
                after_compare="0" * 64, project_root=project,
            )
            self.assertEqual(result.exit_code, 1)
            self.assertTrue(any("hash" in e for e in result.errors), msg=result.errors)

    def test_export_refused_when_source_changed_after_compare(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            support.run("init", project_root=project)
            _establish_baseline(project)
            records_path = support.build_records(project, PERIOD_2)
            _run(cli.cmd_compare, period=PERIOD_2, out=None, project_root=project)
            stored_hash = _compare_hash(project)

            # Simulate a source change landing after the compare: the records the
            # export would use no longer match what was acknowledged.
            doc = json.loads(records_path.read_text(encoding="utf-8"))
            doc["records"]["company_update"][0]["fields"]["current_ftes"] = 999
            records_path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            result = _run(
                cli.cmd_export, period=PERIOD_2, out=None,
                after_compare=stored_hash, project_root=project,
            )
            self.assertEqual(result.exit_code, 1)
            self.assertTrue(any("source changed" in e for e in result.errors), msg=result.errors)

    def test_export_refused_when_prior_baseline_changed(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            support.run("init", project_root=project)
            _establish_baseline(project)
            support.build_records(project, PERIOD_2)
            _run(cli.cmd_compare, period=PERIOD_2, out=None, project_root=project)
            stored_hash = _compare_hash(project)

            baseline_path = compare.baseline_path(project, PERIOD_1)
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            baseline["records"]["company"][0]["fields"]["legal_name"] = "Tampered Inc"
            baseline_path.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            result = _run(
                cli.cmd_export, period=PERIOD_2, out=None,
                after_compare=stored_hash, project_root=project,
            )
            self.assertEqual(result.exit_code, 1)
            self.assertTrue(any("baseline changed" in e for e in result.errors), msg=result.errors)

    def test_plain_export_without_gate_still_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            support.run("init", project_root=project)
            support.build_records(project, PERIOD_2)
            result = _run(cli.cmd_export, period=PERIOD_2, out=None, after_compare=None, project_root=project)
            self.assertIn(result.exit_code, (0, 2), msg=result.errors)


class IdempotenceTests(unittest.TestCase):
    def test_same_period_rerun_is_idempotent_and_never_self_compares(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            support.run("init", project_root=project)
            _establish_baseline(project)
            support.build_records(project, PERIOD_2)

            _run(cli.cmd_compare, period=PERIOD_2, out=None, project_root=project)
            first = support.load_json(project / "workspace" / "reports" / PERIOD_2 / "compare.json")
            # Re-run the very same period.
            _run(cli.cmd_compare, period=PERIOD_2, out=None, project_root=project)
            second = support.load_json(project / "workspace" / "reports" / PERIOD_2 / "compare.json")

            self.assertEqual(first, second)  # byte-for-byte idempotent
            self.assertEqual(first["baseline_period"], PERIOD_1)  # prior period, never itself
            self.assertNotEqual(first["baseline_period"], PERIOD_2)


if __name__ == "__main__":
    unittest.main()
