PYTHON ?= python3

.PHONY: check release-check test schema pii scan preflight fixtures manifest deps store-test help

help:
	@echo "make check          - run tests + JSON Schema validation + PII/secret scan + CLI scan"
	@echo "make release-check   - verify release-manifest.json sha256 against files"
	@echo "make test            - run the test suite (stdlib unittest)"
	@echo "make store-test      - apply store migrations + seeds to a local Supabase stack and run the pgTAP access proofs"
	@echo "make schema          - validate every contract file against its JSON Schema"
	@echo "make pii             - run the PII / secret / agreement scan over fixtures"
	@echo "make scan            - run the impactos CLI secret/PII scan over tracked files"
	@echo "make preflight       - report interpreter, vendored openpyxl and workspace"
	@echo "make fixtures        - regenerate the synthetic Harbourline fixture"
	@echo "make manifest        - regenerate contract/release-manifest.json"
	@echo "make deps            - install the single dev dependency (jsonschema)"

# jsonschema is the ONLY non-standard-library dependency, and it is dev/test
# only: the contract files themselves (consumed by other children) need nothing.
deps:
	@$(PYTHON) -c "import jsonschema" 2>/dev/null || $(PYTHON) -m pip install --quiet jsonschema

check: deps schema test pii scan
	@echo "make check: OK"

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

release-check:
	@$(PYTHON) tools/release_manifest.py check

fixtures:
	@$(PYTHON) tools/build_fixtures.py

manifest:
	@$(PYTHON) tools/release_manifest.py generate
