"""SR-14: `brief` builds a valid A2UI v0.9.1 blueprint and an equivalent
Markdown document from the file-route records.

Proves:

* the generated messages validate against the A2UI v0.9.1 message schema and the
  eight-component catalogue (and that the validator can actually fail);
* the Markdown matches a committed golden for a company, the portfolio, and a
  company with no interactions (empty state);
* the brief is display-only (no Button, Input, Select or action);
* the committed blueprint fixture the renderer smoke test loads equals a fresh
  build, so the renderer proof stays in sync with the builder.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import impactos_support as support

from impactos_agent import a2ui, brief

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "fixtures" / "brief"
RECORDS = FIXTURE_DIR / "records.json"
EXPECTED = FIXTURE_DIR / "expected"
BLUEPRINT_FIXTURE = FIXTURE_DIR / "company-ACME-1.blueprint.json"

DISPLAY_ONLY_FORBIDDEN = {"Button", "Input", "Select"}


def load_document():
    return json.loads(RECORDS.read_text(encoding="utf-8"))


def components_of(messages):
    comps = []
    for message in messages:
        if "updateComponents" in message:
            comps.extend(message["updateComponents"]["components"])
    return comps


class SchemaAndCatalogueTests(unittest.TestCase):
    def test_company_blueprint_is_schema_and_catalogue_valid(self):
        built = brief.build_company_brief(load_document(), "ACME-1")
        self.assertEqual(a2ui.validate_messages(built["messages"]), [])
        # createSurface must name the catalogue the renderer registers.
        create = built["messages"][0]["createSurface"]
        self.assertEqual(create["catalogId"], a2ui.CATALOG_ID)
        for message in built["messages"]:
            self.assertEqual(message["version"], "v0.9.1")

    def test_portfolio_blueprint_is_schema_and_catalogue_valid(self):
        built = brief.build_portfolio_brief(load_document())
        self.assertEqual(a2ui.validate_messages(built["messages"]), [])

    def test_only_catalogue_components_used(self):
        for messages in (
            brief.build_company_brief(load_document(), "ACME-1")["messages"],
            brief.build_portfolio_brief(load_document())["messages"],
        ):
            for comp in components_of(messages):
                self.assertIn(comp["component"], a2ui.CATALOG_COMPONENTS)

    def test_validator_rejects_a_broken_blueprint(self):
        # A check that could not fail proves nothing: corrupt the blueprint and
        # confirm the validator catches an off-catalogue component, a bad enum,
        # a dangling child reference and a wrong catalogId.
        errors = a2ui.validate_messages([
            {"version": "v0.9.1", "createSurface": {"surfaceId": "brief", "catalogId": "wrong"}},
            {"version": "v0.9.1", "updateComponents": {"surfaceId": "brief", "components": [
                {"id": "root", "component": "Column", "children": ["ghost"]},
                {"id": "x", "component": "Accordion"},
                {"id": "y", "component": "Text", "text": "hi", "variant": "huge"},
            ]}},
        ])
        joined = " | ".join(errors)
        self.assertIn("catalogId", joined)
        self.assertIn("Accordion", joined)
        self.assertIn("variant", joined)
        self.assertIn("ghost", joined)


class MarkdownGoldenTests(unittest.TestCase):
    def test_company_markdown_matches_golden(self):
        built = brief.build_company_brief(load_document(), "ACME-1")
        self.assertEqual(built["markdown"], (EXPECTED / "company-ACME-1.md").read_text(encoding="utf-8"))

    def test_portfolio_markdown_matches_golden(self):
        built = brief.build_portfolio_brief(load_document())
        self.assertEqual(built["markdown"], (EXPECTED / "portfolio.md").read_text(encoding="utf-8"))

    def test_empty_state_company_markdown_matches_golden(self):
        built = brief.build_company_brief(load_document(), "ACME-2")
        self.assertEqual(built["markdown"], (EXPECTED / "company-ACME-2.md").read_text(encoding="utf-8"))


class EmptyStateTests(unittest.TestCase):
    def test_company_with_no_interactions_renders_empty_state(self):
        built = brief.build_company_brief(load_document(), "ACME-2")
        ids = {comp["id"] for comp in components_of(built["messages"])}
        self.assertIn("interactions-empty", ids)
        self.assertNotIn("interactions-table", ids)
        self.assertEqual(built["data_model"]["interactions"], [])

    def test_company_with_interactions_shows_at_most_three(self):
        built = brief.build_company_brief(load_document(), "ACME-1")
        interactions = built["data_model"]["interactions"]
        self.assertEqual(len(interactions), 3)
        # Most recent first.
        self.assertEqual([i["date"] for i in interactions], ["2026-06-01", "2026-05-15", "2026-04-20"])


class DisplayOnlyTests(unittest.TestCase):
    def test_no_actions_or_input_components(self):
        for company_id in ("ACME-1", "ACME-2"):
            for comp in components_of(brief.build_company_brief(load_document(), company_id)["messages"]):
                self.assertNotIn(comp["component"], DISPLAY_ONLY_FORBIDDEN)
                self.assertNotIn("action", comp)
        for comp in components_of(brief.build_portfolio_brief(load_document())["messages"]):
            self.assertNotIn(comp["component"], DISPLAY_ONLY_FORBIDDEN)
            self.assertNotIn("action", comp)


class BlueprintFixtureTests(unittest.TestCase):
    def test_committed_blueprint_fixture_equals_fresh_build(self):
        built = brief.build_company_brief(load_document(), "ACME-1")
        committed = json.loads(BLUEPRINT_FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(committed, built["messages"],
                         "fixtures/brief/company-ACME-1.blueprint.json is stale; the renderer "
                         "smoke test loads it, so rebuild it from the current builder")


class CliTests(unittest.TestCase):
    def test_cli_writes_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            result = support.run(
                "brief", company="ACME-1", portfolio=False, records=str(RECORDS),
                period=None, out=str(out), project_root=Path(tmp),
            )
            self.assertEqual(result.exit_code, 0, msg=result.errors)
            self.assertTrue((out / "company-ACME-1.json").exists())
            self.assertTrue((out / "company-ACME-1.md").exists())

    def test_cli_refuses_without_a_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = support.run(
                "brief", company=None, portfolio=False, records=str(RECORDS),
                period=None, out=str(tmp), project_root=Path(tmp),
            )
            self.assertEqual(result.exit_code, 1)

    def test_cli_reports_unknown_company(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = support.run(
                "brief", company="NOPE", portfolio=False, records=str(RECORDS),
                period=None, out=str(tmp), project_root=Path(tmp),
            )
            self.assertEqual(result.exit_code, 1)
            self.assertTrue(any("NOPE" in e for e in result.errors))


if __name__ == "__main__":
    unittest.main()
