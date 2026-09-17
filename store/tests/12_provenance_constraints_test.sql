-- SR-19: every fact carries provenance. The fact_provenance table makes the
-- source columns NOT NULL and keys the row to a company and a write batch, and an
-- insert that omits provenance detail fails.
begin;
select plan(8);

-- NOT NULL on the provenance identity columns.
select col_not_null('public', 'fact_provenance', 'source_system', 'fact_provenance.source_system is NOT NULL');
select col_not_null('public', 'fact_provenance', 'source_id',     'fact_provenance.source_id is NOT NULL');
select col_not_null('public', 'fact_provenance', 'fact_table',    'fact_provenance.fact_table is NOT NULL');

-- Foreign keys tie provenance to its batch and company.
select col_is_fk('public', 'fact_provenance', 'write_batch_id', 'fact_provenance.write_batch_id is a foreign key');
select col_is_fk('public', 'fact_provenance', 'company_id',     'fact_provenance.company_id is a foreign key');

-- acceptance_rule keeps its route domain.
select col_not_null('public', 'acceptance_rule', 'route', 'acceptance_rule.route is NOT NULL');
select ok(
  (select count(*)::int from public.acceptance_rule where route not in ('auto_accept','review','reject')) = 0,
  'every acceptance_rule route is a known route');

-- An insert without the required provenance identity fails (as staff).
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000001","role":"authenticated"}', true);
select throws_ok(
  $$insert into public.fact_provenance (source_id, fact_table) values ('x','company_update')$$,
  '23502', NULL, 'a provenance row without source_system is rejected');
reset role;

select * from finish();
rollback;
