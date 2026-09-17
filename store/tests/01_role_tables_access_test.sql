-- Role tables: app_role, app_user, user_role, company_assignment, company_person.
-- Proves both halves: each declared audience reaches its rows, and excluded
-- callers do not. Fixtures are seeded by store/seed/fixture.sql before this runs.
begin;
select plan(18);

-- ---- app_role: any authenticated user reads the role catalogue. -------------
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000004","role":"authenticated"}', true);
select is((select count(*)::int from public.app_role), 5, 'coach reads the five role names');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000006","role":"authenticated"}', true);
select is((select count(*)::int from public.app_role), 5, 'founder reads the five role names');
reset role;

-- ---- app_user: own row for non-staff; all rows for staff. -------------------
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000001","role":"authenticated"}', true);
select is((select count(*)::int from public.app_user), 6, 'staff reads every app_user');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000004","role":"authenticated"}', true);
select is((select count(*)::int from public.app_user), 1, 'coach reads only their own app_user row');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000003","role":"authenticated"}', true);
select is((select count(*)::int from public.app_user), 1, 'ended helper reads only their own app_user row');
reset role;

-- ---- user_role: own rows for non-staff; all for staff. ----------------------
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000001","role":"authenticated"}', true);
select is((select count(*)::int from public.user_role), 6, 'staff reads every user_role');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000006","role":"authenticated"}', true);
select is((select count(*)::int from public.user_role), 1, 'founder reads only their own user_role');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000003","role":"authenticated"}', true);
select is((select count(*)::int from public.user_role), 1, 'ended helper reads only their own user_role');
reset role;

-- ---- company_assignment: own rows for non-staff; all for staff. -------------
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000001","role":"authenticated"}', true);
select is((select count(*)::int from public.company_assignment), 5, 'staff reads every company_assignment');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000004","role":"authenticated"}', true);
select is((select count(*)::int from public.company_assignment), 3, 'coach reads their three assignments');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000003","role":"authenticated"}', true);
select is((select count(*)::int from public.company_assignment), 0, 'ended helper has no assignment rows');
reset role;

-- ---- company_person: rows for a company you can see. ------------------------
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000001","role":"authenticated"}', true);
select is((select count(*)::int from public.company_person), 3, 'staff reads every company_person');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000004","role":"authenticated"}', true);
select is((select count(*)::int from public.company_person), 2, 'coach reads company_person for assigned companies (A,B)');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000006","role":"authenticated"}', true);
select is((select count(*)::int from public.company_person), 1, 'founder reads company_person for their own company');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000003","role":"authenticated"}', true);
select is((select count(*)::int from public.company_person), 0, 'ended helper reads no company_person');
reset role;

-- ---- Writes: only staff/helper may write the role/link tables. --------------
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000004","role":"authenticated"}', true);
select throws_ok(
  $$insert into public.company_assignment (user_id, company_id, role_id)
     select '11111111-0000-4000-8000-000000000004','22222222-0000-4000-8000-0000000000dd', id
     from public.app_role where name='coach'$$,
  '42501', NULL, 'coach cannot grant themselves a company assignment');
select throws_ok(
  $$insert into public.user_role (user_id, role_id)
     select '11111111-0000-4000-8000-000000000004', id from public.app_role where name='staff'$$,
  '42501', NULL, 'coach cannot grant themselves the staff role');
reset role;

set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000001","role":"authenticated"}', true);
select lives_ok(
  $$insert into public.company_assignment (user_id, company_id, role_id)
     select '11111111-0000-4000-8000-000000000005','22222222-0000-4000-8000-0000000000bb', id
     from public.app_role where name='advisor'$$,
  'staff can create a company assignment');
reset role;

select * from finish();
rollback;
