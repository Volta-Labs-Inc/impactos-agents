-- Company-scoped tables: company, company_update, funding_event,
-- team_member_period, membership, milestone_position, milestone_target.
-- Staff/helper see all; coach and advisor see assigned companies; a founder sees
-- their own company; an ended helper sees nothing. Both halves, every role.
begin;
select plan(40);

-- ---- staff: everything. -----------------------------------------------------
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000001","role":"authenticated"}', true);
select is((select count(*)::int from public.company), 4, 'staff sees all companies');
select is((select count(*)::int from public.company_update), 2, 'staff sees all company_update');
select is((select count(*)::int from public.funding_event), 1, 'staff sees all funding_event');
select is((select count(*)::int from public.team_member_period), 1, 'staff sees all team_member_period');
select is((select count(*)::int from public.membership), 1, 'staff sees all membership');
select is((select count(*)::int from public.milestone_position), 1, 'staff sees all milestone_position');
select is((select count(*)::int from public.milestone_target), 1, 'staff sees all milestone_target');
reset role;

-- ---- coach: assigned companies A,B,C. --------------------------------------
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000004","role":"authenticated"}', true);
select is((select count(*)::int from public.company), 3, 'coach sees three assigned companies');
select is((select count(*)::int from public.company_update), 2, 'coach sees updates for A and B');
select is((select count(*)::int from public.funding_event), 1, 'coach sees funding for A');
select is((select count(*)::int from public.team_member_period), 1, 'coach sees team period for A');
select is((select count(*)::int from public.membership), 1, 'coach sees membership for A');
select is((select count(*)::int from public.milestone_position), 1, 'coach sees milestone position for A');
select is((select count(*)::int from public.milestone_target), 1, 'coach sees milestone target for A');
select is((select count(*)::int from public.company where id='22222222-0000-4000-8000-0000000000dd'), 0, 'coach cannot see the unassigned company D');
reset role;

-- ---- advisor: assigned company A only. -------------------------------------
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000005","role":"authenticated"}', true);
select is((select count(*)::int from public.company), 1, 'advisor sees one assigned company');
select is((select count(*)::int from public.company_update), 1, 'advisor sees updates for A');
select is((select count(*)::int from public.funding_event), 1, 'advisor sees funding for A');
select is((select count(*)::int from public.team_member_period), 1, 'advisor sees team period for A');
select is((select count(*)::int from public.membership), 1, 'advisor sees membership for A');
select is((select count(*)::int from public.milestone_position), 1, 'advisor sees milestone position for A');
select is((select count(*)::int from public.milestone_target), 1, 'advisor sees milestone target for A');
reset role;

-- ---- founder: own company A only. ------------------------------------------
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000006","role":"authenticated"}', true);
select is((select count(*)::int from public.company), 1, 'founder sees only their own company');
select is((select count(*)::int from public.company_update), 1, 'founder sees updates for their company');
select is((select count(*)::int from public.funding_event), 1, 'founder sees funding for their company');
select is((select count(*)::int from public.team_member_period), 1, 'founder sees team period for their company');
select is((select count(*)::int from public.membership), 1, 'founder sees membership for their company');
select is((select count(*)::int from public.milestone_position), 1, 'founder sees milestone position for their company');
select is((select count(*)::int from public.milestone_target), 1, 'founder sees milestone target for their company');
select is((select count(*)::int from public.company where id='22222222-0000-4000-8000-0000000000bb'), 0, 'founder cannot see another company');
reset role;

-- ---- ended helper: nothing. ------------------------------------------------
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000003","role":"authenticated"}', true);
select is((select count(*)::int from public.company), 0, 'ended helper sees no company');
select is((select count(*)::int from public.company_update), 0, 'ended helper sees no company_update');
select is((select count(*)::int from public.funding_event), 0, 'ended helper sees no funding_event');
select is((select count(*)::int from public.team_member_period), 0, 'ended helper sees no team_member_period');
select is((select count(*)::int from public.membership), 0, 'ended helper sees no membership');
select is((select count(*)::int from public.milestone_position), 0, 'ended helper sees no milestone_position');
select is((select count(*)::int from public.milestone_target), 0, 'ended helper sees no milestone_target');
reset role;

-- ---- writes are staff/helper only. -----------------------------------------
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000004","role":"authenticated"}', true);
select throws_ok(
  $$insert into public.company (source_system, source_id, legal_name) values ('t','coach-x','X')$$,
  '42501', NULL, 'coach cannot insert a company');
reset role;
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000006","role":"authenticated"}', true);
select throws_ok(
  $$insert into public.company (source_system, source_id, legal_name) values ('t','founder-x','X')$$,
  '42501', NULL, 'founder cannot insert a company');
reset role;
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000001","role":"authenticated"}', true);
select lives_ok(
  $$insert into public.company (source_system, source_id, legal_name) values ('t','staff-x','X')$$,
  'staff can insert a company');
reset role;

select * from finish();
rollback;
