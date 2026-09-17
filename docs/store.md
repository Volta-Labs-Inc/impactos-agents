# The impactOS store

The store is the optional database an organisation can move data into, instead of
leaving every fact in its existing systems. This document is the operating record
for it: who reads it, where the credentials live, exactly who is allowed to see
what, and how that is proven.

This issue (6a) ships the store's shape, its access rules, per-user sign-in, and
provisioning. Writing facts into the store, retraction, the founder queue, and
building reports or briefs from the store are a later increment (6b). The store
route is proven on a disposable fixture only; a real organisation adopting it is a
later milestone.

## Who uses this database

Only two things ever talk to the store, and both do so as the signed-in person,
never with an administrator key:

- the `impactos` command-line tool (this repository), and
- the founder shim that arrives in 6b.

No website, scheduled job, edge function, or reporting script reads or writes it.
If that ever changes, the new reader must be added here first, and its access
rules written before it connects.

## Where the credentials live

- **Each person's session.** Signing in with `impactos store login` gets a
  per-user session (an access token and a refresh token) from Supabase Auth,
  requested with the project's *publishable* key — a value that is safe to share.
  The session is written to `workspace/config.json`, which is never committed. The
  session is refreshed automatically when it expires.
- **The provisioning token.** `impactos store provision` applies the migrations
  through Supabase's management API using the personal access token that
  `supabase login` stores in the operating system's keychain (on macOS, the login
  keychain under the service name "Supabase CLI"). The tool reads it from there at
  the moment it provisions and never prints, copies, or writes it.
- **What is never held anywhere.** There is no service-role (admin) key and no
  database password in this repository, in the CLI code, in `workspace/`, or in
  the tool's memory. Provisioning refuses to run if a secret is passed on the
  command line or through an environment variable, so none can be smuggled in.

`workspace/config.json` therefore holds only a public key and the current
person's session — nothing that grants administrator access.

## Who can see what

Every table has row-level security switched on, and the anonymous public is
granted nothing at all. A person only ever sees rows their active role allows.
Roles can be time-bounded: a helper's access ends the moment its end date passes.

| Data | Staff / active helper | Coach / advisor | Founder | Anonymous |
|---|---|---|---|---|
| `app_role` (role names) | read | read (any signed-in user) | read | none |
| `app_user`, `user_role`, `company_assignment` | all | own rows | own rows | none |
| `company_person` | all | own company's rows | own company's rows | none |
| `organization`, `program`, `cohort`, `milestone_track`, `milestone_definition` | read + write | read | read | none |
| `company`, `company_update`, `funding_event`, `team_member_period`, `membership`, `milestone_position`, `milestone_target` | all | assigned companies | own company | none |
| `interaction`, `interaction_participant` | all | assigned companies | **none** | none |
| `person` (name, contact) | all | people at assigned companies | **none directly** (only `person_public`) | none |
| `person_demographics` | **only staff / active helper** | none | none | none |
| `submission` | all | none | insert + read own company's rows (only as "pending"); no update or delete | none |
| `fact_provenance`, `retraction`, `write_batch` | all | rows for a company they can see | rows for their company | none |

Two boundaries carry the most weight and are worth stating plainly:

- **A founder never sees another company, never sees interactions, and never sees
  a person's contact details.** The only way a founder sees people is through the
  `person_public` view, which shows just a display name and a role for people at
  their own company. Everything else about a person is invisible to them.
- **Self-identified demographics are visible to staff and an active helper only.**
  They live in their own table (`person_demographics`), no policy anywhere else
  grants them, and no view reads them — so a coach, advisor, or founder cannot
  reach them by any path.

An ended helper is the negative case that ties this together: once its end date
passes, it sees zero rows on every data table. The only thing still visible to it
is the list of role names, which carries no company, personal, or financial data.

## How the rules are enforced (for reviewers)

- Only the `public` schema is exposed to the API, so every function the CLI calls
  lives there. The caller-identity helper `app.uid()` sits in a separate,
  unexposed `app` schema.
- Access decisions run through two small functions, `role_active(name)` and
  `can_see_company(id)`. Both check only facts about the *caller*, both return
  false for a signed-out caller, both are revoked from everyone and granted only
  to signed-in users, and both run with elevated rights solely so they can read
  the membership tables without the row rules on those tables referring back to
  themselves.
- Every export view is created so that it runs with the caller's own permissions.
  The single exception is `person_public`, which is deliberately owner-run so it
  can project people past the `person` table's rules — and every row it returns is
  gated by `can_see_company`, so it can never widen what a caller sees.
- Grants are explicit. New tables are created with no access for the anonymous or
  the generic signed-in role, and each table is then granted exactly the commands
  its rules need.

## Advisor baseline

Supabase ships a security-and-performance advisor. Because this schema is created
on a fresh project, the baseline to compare against is that fresh project's
advisor output *immediately after the migrations are applied*. The procedure:

1. On the freshly provisioned project, run the advisors for both the `security`
   and `performance` types (`get_advisors` on the Supabase MCP server, or
   `supabase db advisors`).
2. Record each finding's name and object — not just a count — as the baseline.
3. Any finding this schema introduces is a defect to fix before shipping. A
   finding that pre-exists on a bare Supabase project is not this schema's
   problem, but must not be silently absorbed.

The advisor sees protection toggles and definer objects; it cannot see what a
policy permits. It is one check, not the whole proof — the access proofs below are.

## How the access rules are proven

The proofs run as real roles (the anonymous role, and a signed-in user with a
real subject), because only that can tell a working rule from an open table.

- **Access proofs (`store/tests/*_test.sql`, pgTAP).** For every table, every
  declared audience is shown to reach its rows and every excluded caller is shown
  to reach none — including the ended helper (zero everywhere), the anonymous
  public (denied), a founder (no interactions, no direct person rows, no other
  company, no demographics), and a coach limited to assigned companies. Function
  privileges and view options are asserted too.
- **Contract parity (`tests/test_contract_parity.py`).** The applied schema is
  checked column-by-column against `contract/data-contract.json`: types, required
  fields, the money shape, and that demographic columns live only in
  `person_demographics`.
- **CLI behaviour (`tests/test_store_cli.py`).** Sign-in, the refresh-on-expiry
  retry, the provisioning gate, the secret-smuggling refusals, and the explicit
  "access denied" answer.

Run the access proofs against a local Supabase Postgres cluster:

```
supabase start           # provides a local cluster
make store-test          # applies migrations + seeds and runs the pgTAP proofs
```

`make store-test` creates a fresh, isolated database inside the running cluster,
applies the migrations and the fixture, runs every pgTAP suite, and drops the
database. Point it at a specific cluster with
`IMPACTOS_STORE_DB_CONTAINER=<supabase_db_container>` if more than one is running.
`make check` never depends on Docker; the parity test skips when no cluster is
available.
