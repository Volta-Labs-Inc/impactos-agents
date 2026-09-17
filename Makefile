PYTHON ?= python3

.PHONY: check release-check test schema pii scan preflight fixtures manifest deps store-test help
.PHONY: check release-check test schema pii scan preflight fixtures manifest deps help mirror mirror-check fixture-store

help:
	@echo "make check          - run tests + JSON Schema validation + PII/secret scan + CLI scan + skills mirror check"
	@echo "make release-check   - verify release-manifest.json sha256 against files"
	@echo "make test            - run the test suite (stdlib unittest)"
	@echo "make store-test      - apply store migrations + seeds to a local Supabase stack and run the pgTAP access proofs"
	@echo "make fixture-store   - run the store route end to end against a live fixture project (needs a provisioned project; see store/fixture/fixture_store.sh)"
	@echo "make schema          - validate every contract file against its JSON Schema"
	@echo "make pii             - run the PII / secret / agreement scan over fixtures"
	@echo "make scan            - run the impactos CLI secret/PII scan over tracked files"
	@echo "make preflight       - report interpreter, vendored openpyxl and workspace"
	@echo "make fixtures        - regenerate the synthetic Harbourline fixture"
	@echo "make manifest        - regenerate contract/release-manifest.json"
	@echo "make deps            - install the single dev dependency (jsonschema)"
	@echo "make mirror          - mirror skills/ into .claude/skills/ and .agents/skills/"
	@echo "make mirror-check    - fail if the skills mirrors have drifted from skills/"

# jsonschema is the ONLY non-standard-library dependency, and it is dev/test
# only: the contract files themselves (consumed by other children) need nothing.
deps:
	@$(PYTHON) -c "import jsonschema" 2>/dev/null || $(PYTHON) -m pip install --quiet jsonschema

check: deps schema test pii scan mirror-check
	@echo "make check: OK"

mirror:
	@$(PYTHON) scripts/sync_skills.py

mirror-check:
	@$(PYTHON) scripts/sync_skills.py --check

# The deterministic CLI ships with the repo (vendored openpyxl); no install step.
scan:
	@$(PYTHON) cli/run.py check --tracked

preflight:
	@$(PYTHON) cli/run.py preflight

schema:
	@$(PYTHON) tools/validate_contracts.py

pii:
	@$(PYTHON) tools/pii_scan.py

test:
	@$(PYTHON) -m unittest discover -s tests -v

# Runs the store pgTAP access proofs against a local Supabase Postgres cluster
# (needs Docker + `supabase start`). Not part of `make check`, which must stay
# green in environments without Docker.
store-test:
	@bash store/tests/run.sh

# End-to-end store journey against a LIVE provisioned fixture project (network).
# Not part of `make check`. See the script header for the environment it needs.
fixture-store:
	@bash store/fixture/fixture_store.sh

release-check:
	@$(PYTHON) tools/release_manifest.py check

fixtures:
	@$(PYTHON) tools/build_fixtures.py

manifest:
	@$(PYTHON) tools/release_manifest.py generate
