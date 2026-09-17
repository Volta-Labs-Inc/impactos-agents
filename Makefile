PYTHON ?= python3

.PHONY: check release-check test schema pii fixtures manifest deps help

help:
	@echo "make check          - run tests + JSON Schema validation + PII/secret scan"
	@echo "make release-check   - verify release-manifest.json sha256 against files"
	@echo "make test            - run the test suite (stdlib unittest)"
	@echo "make schema          - validate every contract file against its JSON Schema"
	@echo "make pii             - run the PII / secret / agreement scan over fixtures"
	@echo "make fixtures        - regenerate the synthetic Harbourline fixture"
	@echo "make manifest        - regenerate contract/release-manifest.json"
	@echo "make deps            - install the single dev dependency (jsonschema)"

# jsonschema is the ONLY non-standard-library dependency, and it is dev/test
# only: the contract files themselves (consumed by other children) need nothing.
deps:
	@$(PYTHON) -c "import jsonschema" 2>/dev/null || $(PYTHON) -m pip install --quiet jsonschema

check: deps schema test pii
	@echo "make check: OK"

schema:
	@$(PYTHON) tools/validate_contracts.py

pii:
	@$(PYTHON) tools/pii_scan.py

test:
	@$(PYTHON) -m unittest discover -s tests -v

release-check:
	@$(PYTHON) tools/release_manifest.py check

fixtures:
	@$(PYTHON) tools/build_fixtures.py

manifest:
	@$(PYTHON) tools/release_manifest.py generate
