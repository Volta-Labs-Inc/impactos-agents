-- Interactions: staff/helper all; coach and advisor for assigned companies;
-- a founder sees NONE, even for their own company.
begin;
select plan(12);

-- staff
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000001","role":"authenticated"}', true);
select is((select count(*)::int from public.interaction), 1, 'staff sees the interaction');
select is((select count(*)::int from public.interaction_participant), 1, 'staff sees the participant');
reset role;

-- coach (assigned to A)
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000004","role":"authenticated"}', true);
select is((select count(*)::int from public.interaction), 1, 'coach sees interaction for assigned company');
select is((select count(*)::int from public.interaction_participant), 1, 'coach sees participant for assigned company');
reset role;

-- advisor (assigned to A)
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000005","role":"authenticated"}', true);
select is((select count(*)::int from public.interaction), 1, 'advisor sees interaction for assigned company');
select is((select count(*)::int from public.interaction_participant), 1, 'advisor sees participant for assigned company');
reset role;

-- founder: none
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000006","role":"authenticated"}', true);
select is((select count(*)::int from public.interaction), 0, 'founder sees no interactions, even for own company');
select is((select count(*)::int from public.interaction_participant), 0, 'founder sees no interaction participants');
reset role;

-- ended helper: none
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000003","role":"authenticated"}', true);
select is((select count(*)::int from public.interaction), 0, 'ended helper sees no interactions');
select is((select count(*)::int from public.interaction_participant), 0, 'ended helper sees no participants');
reset role;

-- writes are staff/helper only
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000004","role":"authenticated"}', true);
select throws_ok(
  $$insert into public.interaction (source_system, source_id, interaction_type, occurred_at, company_id)
     values ('t','coach-i','note', current_date, '22222222-0000-4000-8000-0000000000aa')$$,
  '42501', NULL, 'coach cannot insert an interaction');
reset role;
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000001","role":"authenticated"}', true);
select lives_ok(
  $$insert into public.interaction (source_system, source_id, interaction_type, occurred_at, company_id)
     values ('t','staff-i','note', current_date, '22222222-0000-4000-8000-0000000000aa')$$,
  'staff can insert an interaction');
reset role;

select * from finish();
rollback;
