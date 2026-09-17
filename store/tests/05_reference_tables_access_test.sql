-- Reference tables: organization, program, cohort, milestone_track,
-- milestone_definition. Every active role reads them; only staff/helper write;
-- an ended helper sees nothing.
begin;
select plan(21);

-- organization (all five active roles read)
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000001","role":"authenticated"}', true);
select is((select count(*)::int from public.organization), 1, 'staff reads organization');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000004","role":"authenticated"}', true);
select is((select count(*)::int from public.organization), 1, 'coach reads organization');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000005","role":"authenticated"}', true);
select is((select count(*)::int from public.organization), 1, 'advisor reads organization');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000006","role":"authenticated"}', true);
select is((select count(*)::int from public.organization), 1, 'founder reads organization');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000003","role":"authenticated"}', true);
select is((select count(*)::int from public.organization), 0, 'ended helper reads no organization');
reset role;

-- program
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000001","role":"authenticated"}', true);
select is((select count(*)::int from public.program), 1, 'staff reads program');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000004","role":"authenticated"}', true);
select is((select count(*)::int from public.program), 1, 'coach reads program');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000006","role":"authenticated"}', true);
select is((select count(*)::int from public.program), 1, 'founder reads program');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000003","role":"authenticated"}', true);
select is((select count(*)::int from public.program), 0, 'ended helper reads no program');
reset role;

-- cohort
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000001","role":"authenticated"}', true);
select is((select count(*)::int from public.cohort), 1, 'staff reads cohort');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000004","role":"authenticated"}', true);
select is((select count(*)::int from public.cohort), 1, 'coach reads cohort');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000006","role":"authenticated"}', true);
select is((select count(*)::int from public.cohort), 1, 'founder reads cohort');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000003","role":"authenticated"}', true);
select is((select count(*)::int from public.cohort), 0, 'ended helper reads no cohort');
reset role;

-- milestone_track (four system tracks)
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000001","role":"authenticated"}', true);
select is((select count(*)::int from public.milestone_track), 4, 'staff reads all tracks');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000006","role":"authenticated"}', true);
select is((select count(*)::int from public.milestone_track), 4, 'founder reads all tracks');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000003","role":"authenticated"}', true);
select is((select count(*)::int from public.milestone_track), 0, 'ended helper reads no track');
reset role;

-- milestone_definition (27 rungs across the four tracks)
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000001","role":"authenticated"}', true);
select is((select count(*)::int from public.milestone_definition), 27, 'staff reads all rungs');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000004","role":"authenticated"}', true);
select is((select count(*)::int from public.milestone_definition), 27, 'coach reads all rungs');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000003","role":"authenticated"}', true);
select is((select count(*)::int from public.milestone_definition), 0, 'ended helper reads no rungs');
reset role;

-- writes: founder cannot; staff can.
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000006","role":"authenticated"}', true);
select throws_ok(
  $$insert into public.program (source_system, source_id, name) values ('t','founder-p','P')$$,
  '42501', NULL, 'founder cannot insert a program');
reset role;
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000001","role":"authenticated"}', true);
select lives_ok(
  $$insert into public.program (source_system, source_id, name) values ('t','staff-p','P')$$,
  'staff can insert a program');
reset role;

select * from finish();
rollback;
