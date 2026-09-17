-- Child 6b write path and founder queue (SR-18 idempotency, SR-22 acceptance).
--
-- Proves, as real roles against real policies:
--   * anon cannot execute accept_submission; authenticated can.
--   * a founder cannot insert a fact table directly (6a policy).
--   * accept_submission: a founder is refused a review-required class, refused
--     another company's submission, and accepted for an auto-accept class; a
--     re-accept of an accepted submission is refused; staff accepts a review class.
--   * apply_write_batch is atomic and idempotent: a second call with the same
--     batch id writes nothing (replay no-op); a founder calling it is denied.
begin;
select plan(17);

-- Fixed ids for this suite's submissions (staff seeds them; founder/staff act).
-- company A = ...aa (founder = user 6); company B = ...bb (founder 6 is NOT its founder).

set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000001","role":"authenticated"}', true);
insert into public.submission (id, source_system, source_id, company_id, channel, submitted_at, status, raw_payload_ref) values
  ('55555555-0000-4000-8000-00000000a001','t','sub-auto','22222222-0000-4000-8000-0000000000aa','shim',current_date,'pending',
   '{"fields":[{"field_class":"metric","fact_table":"company_update","record":{"source_system":"fs","source_id":"fs-auto","update_date":"2026-03-31","current_ftes":9}}]}'),
  ('55555555-0000-4000-8000-00000000a002','t','sub-review','22222222-0000-4000-8000-0000000000aa','shim',current_date,'pending',
   '{"fields":[{"field_class":"financial","fact_table":"funding_event","record":{"source_system":"fs","source_id":"fs-review","funding_type":"angel","amount":100000}}]}'),
  ('55555555-0000-4000-8000-00000000b001','t','sub-other','22222222-0000-4000-8000-0000000000bb','shim',current_date,'pending',
   '{"fields":[{"field_class":"metric","fact_table":"company_update","record":{"source_system":"fs","source_id":"fs-other","update_date":"2026-03-31","current_ftes":4}}]}');
reset role;

-- function privileges
select ok(not has_function_privilege('anon', 'public.accept_submission(uuid)', 'EXECUTE'),
  'anon cannot execute accept_submission');
select ok(has_function_privilege('authenticated', 'public.accept_submission(uuid)', 'EXECUTE'),
  'authenticated can execute accept_submission');
select ok(not has_function_privilege('anon', 'public.apply_write_batch(uuid,uuid,text,jsonb)', 'EXECUTE'),
  'anon cannot execute apply_write_batch');

-- a founder cannot write a fact table directly (6a policy)
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000006","role":"authenticated"}', true);
select throws_ok(
  $$insert into public.company_update (source_system, source_id, company_id, update_date)
     values ('t','direct','22222222-0000-4000-8000-0000000000aa',current_date)$$,
  '42501', NULL, 'founder cannot insert a company_update directly');

-- a founder is refused a review-required class
select throws_ok(
  $$select public.accept_submission('55555555-0000-4000-8000-00000000a002')$$,
  '42501', NULL, 'founder cannot accept a review-required (financial) submission');

-- a founder is refused another company's submission
select throws_ok(
  $$select public.accept_submission('55555555-0000-4000-8000-00000000b001')$$,
  '42501', NULL, 'founder cannot accept a submission on a company they do not found');

-- a founder CAN accept an auto-accept-only submission for their own company
select lives_ok(
  $$select public.accept_submission('55555555-0000-4000-8000-00000000a001')$$,
  'founder can accept an auto-accept (metric) submission for their own company');
reset role;

-- the auto-accept produced a fact and marked the submission accepted (read as staff)
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000001","role":"authenticated"}', true);
select is((select status from public.submission where id='55555555-0000-4000-8000-00000000a001'),
  'accepted', 'the accepted submission is marked accepted');
select is((select count(*)::int from public.company_update where source_id='fs-auto'),
  1, 'the founder-submitted metric became a company_update fact');
select is((select count(*)::int from public.fact_provenance where source_system='founder_submission' and source_id like 'sub-auto:%'),
  1, 'provenance attributes the fact to the founder submission');
reset role;

-- re-accepting an accepted submission is refused (as the founder again)
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000006","role":"authenticated"}', true);
select throws_ok(
  $$select public.accept_submission('55555555-0000-4000-8000-00000000a001')$$,
  '42501', NULL, 'an already-accepted submission cannot be accepted again');
reset role;

-- staff CAN accept the review-required submission
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000001","role":"authenticated"}', true);
select lives_ok(
  $$select public.accept_submission('55555555-0000-4000-8000-00000000a002')$$,
  'staff can accept a review-required submission');
select is((select count(*)::int from public.funding_event where source_id='fs-review'),
  1, 'the staff-accepted financial submission became a funding_event fact');
reset role;

-- apply_write_batch: atomic + idempotent (staff), denied to a founder
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000001","role":"authenticated"}', true);
select is(
  (select public.apply_write_batch(
     '66666666-0000-4000-8000-000000000001'::uuid,
     '22222222-0000-4000-8000-0000000000aa'::uuid,
     'batch test',
     '[{"fact_table":"company_update","record":{"source_system":"b","source_id":"batch-u1","update_date":"2026-03-31","current_ftes":11}}]'::jsonb)
   ->> 'status'),
  'applied', 'apply_write_batch applies the batch the first time');
select is(
  (select public.apply_write_batch(
     '66666666-0000-4000-8000-000000000001'::uuid,
     '22222222-0000-4000-8000-0000000000aa'::uuid,
     'batch test',
     '[{"fact_table":"company_update","record":{"source_system":"b","source_id":"batch-u1","update_date":"2026-03-31","current_ftes":11}}]'::jsonb)
   ->> 'status'),
  'noop', 'a replay with the same batch id writes nothing');
select is((select count(*)::int from public.company_update where source_id='batch-u1'),
  1, 'the replayed batch left exactly one fact');
reset role;

set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000006","role":"authenticated"}', true);
select throws_ok(
  $$select public.apply_write_batch(
      '66666666-0000-4000-8000-000000000002'::uuid,
      '22222222-0000-4000-8000-0000000000aa'::uuid,
      'founder batch',
      '[{"fact_table":"company_update","record":{"source_system":"b","source_id":"batch-f1","update_date":"2026-03-31"}}]'::jsonb)$$,
  '42501', NULL, 'a founder cannot write facts through apply_write_batch');
reset role;

select * from finish();
rollback;
