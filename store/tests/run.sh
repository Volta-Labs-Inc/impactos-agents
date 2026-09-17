#!/usr/bin/env bash
#
# Run the impactOS store pgTAP access proofs against a real Supabase Postgres.
#
# The proofs must run as real roles (anon, authenticated with a JWT subject), so
# they need a running Supabase Postgres cluster. This runner creates a fresh,
# isolated database inside that cluster, applies the store migrations and seeds,
# runs every pgTAP suite, then drops the database. It never touches the cluster's
# own `postgres` database.
#
# Provide a cluster one of two ways:
#   * IMPACTOS_STORE_DB_CONTAINER=<name>  a running `supabase_db_*` docker
#     container (e.g. from `supabase start`). This is the default path.
#   * or let the runner auto-discover a single running `supabase_db_*` container.
#
# Overridable:
#   IMPACTOS_STORE_DB_NAME  (default: impactos_store_proof)
#   IMPACTOS_STORE_DB_USER  (default: postgres)
#
# Exit non-zero if any suite fails, errors, or reports a planned/ran mismatch.

set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
store_dir="$(cd "$here/.." && pwd)"
migrations_dir="$store_dir/migrations"
seed_dir="$store_dir/seed"
tests_dir="$store_dir/tests"
bootstrap="$here/harness/local_auth_bootstrap.sql"

db_name="${IMPACTOS_STORE_DB_NAME:-impactos_store_proof}"
db_user="${IMPACTOS_STORE_DB_USER:-postgres}"
container="${IMPACTOS_STORE_DB_CONTAINER:-}"

die() { echo "store-test: $*" >&2; exit 1; }

command -v docker >/dev/null 2>&1 || die "docker is required to run the store access proofs"

if [[ -z "$container" ]]; then
  mapfile -t candidates < <(docker ps --format '{{.Names}}' | grep '^supabase_db_' || true)
  [[ ${#candidates[@]} -eq 1 ]] || die \
    "set IMPACTOS_STORE_DB_CONTAINER to a running supabase_db_* container (found: ${candidates[*]:-none}). Start one with 'supabase start'."
  container="${candidates[0]}"
fi

docker exec -i "$container" psql -U "$db_user" -d postgres -tAc 'select 1' >/dev/null 2>&1 \
  || die "cannot reach postgres in container '$container'"

echo "store-test: cluster container = $container; isolated database = $db_name"

psql_db() { docker exec -i "$container" psql -U "$db_user" -d "$db_name" -v ON_ERROR_STOP=1 -q "$@"; }

# Fresh, isolated database each run.
docker exec -i "$container" dropdb -U "$db_user" --if-exists "$db_name" >/dev/null
docker exec -i "$container" createdb -U "$db_user" "$db_name" >/dev/null

echo "store-test: applying harness bootstrap"
psql_db < "$bootstrap" >/dev/null

echo "store-test: applying migrations"
while IFS= read -r f; do
  echo "  - $(basename "$f")"
  psql_db < "$f" >/dev/null
done < <(find "$migrations_dir" -maxdepth 1 -name '*.sql' | sort)

echo "store-test: applying seeds"
psql_db < "$seed_dir/tracks.sql" >/dev/null
psql_db < "$seed_dir/fixture.sql" >/dev/null

shopt -s nullglob
suites=("$tests_dir"/*_test.sql)
shopt -u nullglob
[[ ${#suites[@]} -gt 0 ]] || die "no *_test.sql suites found in $tests_dir"

echo "store-test: running ${#suites[@]} pgTAP suite(s)"
fail=0
total_ok=0
while IFS= read -r suite; do
  name="$(basename "$suite")"
  out="$(docker exec -i "$container" psql -U "$db_user" -d "$db_name" -P pager=off -f - < "$suite" 2>&1 || true)"
  if grep -qE '^not ok' <<<"$out" \
     || grep -qiE 'Looks like you (planned|failed)' <<<"$out" \
     || grep -qE '^psql:.*ERROR|^ERROR:' <<<"$out"; then
    echo "  FAIL $name"
    grep -E '^not ok|ERROR|Looks like you' <<<"$out" | sed 's/^/      /'
    fail=1
  else
    n_ok="$(grep -cE '^ *ok [0-9]' <<<"$out" || true)"
    total_ok=$((total_ok + n_ok))
    echo "  ok   $name ($n_ok assertions)"
  fi
done < <(printf '%s\n' "${suites[@]}" | sort)

# Clean up the isolated database.
docker exec -i "$container" dropdb -U "$db_user" --if-exists "$db_name" >/dev/null

if [[ "$fail" -ne 0 ]]; then
  die "one or more access proofs failed"
fi
echo "store-test: OK — ${#suites[@]} suite(s), $total_ok assertion(s) passed"
