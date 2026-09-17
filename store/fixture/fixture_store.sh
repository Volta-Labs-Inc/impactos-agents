#!/usr/bin/env bash
#
# End-to-end store route on a disposable fixture project (issue #8 / 6b).
#
# Runs the whole store journey as the CLI a helper would drive:
#   provision -> login (staff) -> ingest fixture -> preview -> confirm ->
#   confirm again (replay no-op) -> retract -> founder submit -> review ->
#   export from store -> brief from store.
#
# This needs a live, provisioned Supabase project with the store migrations
# applied and the fixture identities seeded (store/seed/fixture.sql), reachable
# over its REST and Auth API. It is NOT part of `make check` (which never touches
# a network). Point it at a project with these environment variables:
#
#   IMPACTOS_STORE_API_URL           https://<ref>.supabase.co
#   IMPACTOS_STORE_PUBLISHABLE_KEY   the project's publishable (anon) key
#   IMPACTOS_STORE_STAFF_EMAIL       a staff account (default staff@example.org)
#   IMPACTOS_STORE_STAFF_PASSWORD    its password (default fixturepw)
#   IMPACTOS_STORE_FOUNDER_EMAIL     a founder account (default founder@example.org)
#   IMPACTOS_STORE_FOUNDER_PASSWORD  its password (default fixturepw)
#   IMPACTOS_STORE_COMPANY           the founder's company uuid (default: resolved
#                                    from the seed's company source_id 'company-a')
#   IMPACTOS_STORE_PROJECT_REF       set to also run `store provision` first
#
# Exit non-zero on the first failed step.

set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../.." && pwd)"
cd "$repo"

api_url="${IMPACTOS_STORE_API_URL:-}"
pub_key="${IMPACTOS_STORE_PUBLISHABLE_KEY:-}"
staff_email="${IMPACTOS_STORE_STAFF_EMAIL:-staff@example.org}"
staff_pw="${IMPACTOS_STORE_STAFF_PASSWORD:-fixturepw}"
founder_email="${IMPACTOS_STORE_FOUNDER_EMAIL:-founder@example.org}"
founder_pw="${IMPACTOS_STORE_FOUNDER_PASSWORD:-fixturepw}"
company="${IMPACTOS_STORE_COMPANY:-}"          # resolved after login if empty
company_source_id="${IMPACTOS_STORE_COMPANY_SOURCE_ID:-company-a}"
period="${IMPACTOS_STORE_PERIOD:-2026-06-30}"

die() { echo "fixture-store: $*" >&2; exit 1; }
step() { echo; echo "== fixture-store: $* =="; }

[[ -n "$api_url" && -n "$pub_key" ]] || die \
  "set IMPACTOS_STORE_API_URL and IMPACTOS_STORE_PUBLISHABLE_KEY to a live fixture project"

impactos() { python3 "$repo/cli/run.py" "$@"; }
founder() { python3 "$repo/cli/founder_run.py" "$@"; }

# A tiny helper that reads one value from the store as the current session.
store_get() {  # $1 = REST path+query returning JSON
  python3 - "$1" <<'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, "cli")
from impactos_agent import store
status, body = store.authed_request(Path("."), "GET", sys.argv[1])
if status != 200:
    sys.exit(f"store read failed ({status})")
print(json.dumps(json.loads(body)))
PY
}

if [[ -n "${IMPACTOS_STORE_PROJECT_REF:-}" ]]; then
  step "provision"
  impactos store provision --project-ref "$IMPACTOS_STORE_PROJECT_REF" --api-url "$api_url"
fi

step "login as staff"
impactos store login --email "$staff_email" --password "$staff_pw" \
  --api-url "$api_url" --publishable-key "$pub_key"

if [[ -z "$company" ]]; then
  company="$(store_get "/rest/v1/company?select=id&source_id=eq.$company_source_id&limit=1" | python3 -c 'import json,sys; rows=json.load(sys.stdin); print(rows[0]["id"] if rows else "")')"
  [[ -n "$company" ]] || die "could not resolve company source_id '$company_source_id' from the store"
  echo "resolved company: $company"
fi

step "ingest fixture (parse transcript + CRM, then apply mapping)"
impactos parse --source fixtures/harbourline/transcripts/fireflies-tidewater-2026-04-18.json \
  --type transcript --period "$period"
impactos parse --source "fixtures/harbourline/crm/period-$period/companies.csv" --period "$period"
impactos apply-mapping \
  --source "workspace/sources/$period/companies.source.json" \
  --mapping fixtures/harbourline/mappings/harbourline-crm.json \
  --period "$period" --confirmed

step "preview the write"
hash="$(impactos store write --period "$period" --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["data"]["request_hash"])')"
echo "request hash: $hash"

step "confirm (applies the batch)"
impactos store write --confirm "$hash"

step "confirm again (replay must be a no-op)"
impactos store write --confirm "$hash" --json | python3 -c 'import json,sys; d=json.load(sys.stdin)["data"]; assert d["replayed_noop"], "replay was not a no-op"; print("replay no-op confirmed")'

step "retract a fact (AC-09): the store reader excludes it thereafter"
fact_id="$(store_get "/rest/v1/company_update?select=id&company_id=eq.$company&limit=1" | python3 -c 'import json,sys; rows=json.load(sys.stdin); print(rows[0]["id"] if rows else "")')"
[[ -n "$fact_id" ]] || die "no company_update to retract"
impactos store retract --fact "$fact_id" --fact-table company_update --reason "fixture: superseded value"

step "founder submits a metric via the shim"
printf '%s\n' '{"fields":[{"field_class":"metric","fact_table":"company_update","record":{"source_system":"founder_shim","source_id":"shim-metric-1","update_date":"2026-06-30","current_ftes":8}}]}' > workspace/state/fixture-founder-fields.json
impactos store login --email "$founder_email" --password "$founder_pw" \
  --api-url "$api_url" --publishable-key "$pub_key"
founder submit --company "$company" --fields workspace/state/fixture-founder-fields.json --source-id shim-metric-1
founder status

step "review the submission (staff accepts the auto-accept class)"
impactos store login --email "$staff_email" --password "$staff_pw" \
  --api-url "$api_url" --publishable-key "$pub_key"
sub_id="$(store_get "/rest/v1/submission?select=id&source_id=eq.shim-metric-1&limit=1" | python3 -c 'import json,sys; rows=json.load(sys.stdin); print(rows[0]["id"] if rows else "")')"
[[ -n "$sub_id" ]] || die "founder submission not found"
impactos store review --submission "$sub_id" --accept

step "export from the store (excludes the retracted fact)"
impactos store export --period "$period"

step "brief from the store"
impactos brief --portfolio --from store --period "$period"

echo
echo "fixture-store: OK — full store journey completed against $api_url"
