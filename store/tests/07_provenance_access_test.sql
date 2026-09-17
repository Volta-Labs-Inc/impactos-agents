-- Provenance / write bookkeeping: staff/helper all; coach, advisor and founder
-- read only rows attached to a company they can otherwise see; only staff/helper
-- may insert a retraction.
begin;
select plan(16);

-- write_batch
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000001","role":"authenticated"}', true);
select is((select count(*)::int from public.write_batch), 2, 'staff reads every write_batch');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000004","role":"authenticated"}', true);
select is((select count(*)::int from public.write_batch), 1, 'coach reads only the company-scoped write_batch');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000005","role":"authenticated"}', true);
select is((select count(*)::int from public.write_batch), 1, 'advisor reads only the company-scoped write_batch');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000006","role":"authenticated"}', true);
select is((select count(*)::int from public.write_batch), 1, 'founder reads only the company-scoped write_batch');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000003","role":"authenticated"}', true);
select is((select count(*)::int from public.write_batch), 0, 'ended helper reads no write_batch');
reset role;

-- fact_provenance
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000001","role":"authenticated"}', true);
select is((select count(*)::int from public.fact_provenance), 2, 'staff reads every fact_provenance');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000004","role":"authenticated"}', true);
select is((select count(*)::int from public.fact_provenance), 1, 'coach reads only company-scoped provenance');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000006","role":"authenticated"}', true);
select is((select count(*)::int from public.fact_provenance), 1, 'founder reads only company-scoped provenance');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000003","role":"authenticated"}', true);
select is((select count(*)::int from public.fact_provenance), 0, 'ended helper reads no provenance');
reset role;

-- retraction
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000001","role":"authenticated"}', true);
select is((select count(*)::int from public.retraction), 1, 'staff reads the retraction');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000004","role":"authenticated"}', true);
select is((select count(*)::int from public.retraction), 1, 'coach reads the company-scoped retraction');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000006","role":"authenticated"}', true);
select is((select count(*)::int from public.retraction), 1, 'founder reads the company-scoped retraction');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000003","role":"authenticated"}', true);
select is((select count(*)::int from public.retraction), 0, 'ended helper reads no retraction');
reset role;

-- only staff/helper may insert a retraction
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000004","role":"authenticated"}', true);
select throws_ok(
  $$insert into public.retraction (company_id, fact_table, reason) values ('22222222-0000-4000-8000-0000000000aa','company_update','x')$$,
  '42501', NULL, 'coach cannot insert a retraction');
reset role;
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000006","role":"authenticated"}', true);
select throws_ok(
  $$insert into public.retraction (company_id, fact_table, reason) values ('22222222-0000-4000-8000-0000000000aa','company_update','x')$$,
  '42501', NULL, 'founder cannot insert a retraction');
reset role;
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000001","role":"authenticated"}', true);
select lives_ok(
  $$insert into public.retraction (company_id, fact_table, reason) values ('22222222-0000-4000-8000-0000000000aa','company_update','x')$$,
  'staff can insert a retraction');
reset role;

select * from finish();
rollback;
