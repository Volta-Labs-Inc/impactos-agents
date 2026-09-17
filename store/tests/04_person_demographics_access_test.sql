-- People, demographics and the person_public projection (D-18 column proof).
-- Personal contact rows: staff/helper all; coach/advisor for linked companies;
-- founder none directly. Demographics: staff/helper only, by any path. The only
-- founder view of people is person_public: id, company_id, display_name, role.
begin;
select plan(18);

-- ---- person (direct table) -------------------------------------------------
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000001","role":"authenticated"}', true);
select is((select count(*)::int from public.person), 3, 'staff sees every person');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000004","role":"authenticated"}', true);
select is((select count(*)::int from public.person), 2, 'coach sees persons for assigned companies');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000005","role":"authenticated"}', true);
select is((select count(*)::int from public.person), 1, 'advisor sees persons for the assigned company');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000006","role":"authenticated"}', true);
select is((select count(*)::int from public.person), 0, 'founder sees NO person directly');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000003","role":"authenticated"}', true);
select is((select count(*)::int from public.person), 0, 'ended helper sees no person');
reset role;

-- ---- person_demographics: staff/helper only. -------------------------------
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000001","role":"authenticated"}', true);
select is((select count(*)::int from public.person_demographics), 1, 'staff sees demographics');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000004","role":"authenticated"}', true);
select is((select count(*)::int from public.person_demographics), 0, 'coach sees NO demographics');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000005","role":"authenticated"}', true);
select is((select count(*)::int from public.person_demographics), 0, 'advisor sees NO demographics');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000006","role":"authenticated"}', true);
select is((select count(*)::int from public.person_demographics), 0, 'founder sees NO demographics');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000003","role":"authenticated"}', true);
select is((select count(*)::int from public.person_demographics), 0, 'ended helper sees NO demographics');
reset role;

-- ---- person_public: the founder's only view of people. ---------------------
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000006","role":"authenticated"}', true);
select is((select count(*)::int from public.person_public), 1, 'founder sees people at their own company via person_public');
select is((select count(*)::int from public.person_public where company_id='22222222-0000-4000-8000-0000000000bb'), 0, 'founder sees no other company in person_public');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000004","role":"authenticated"}', true);
select is((select count(*)::int from public.person_public), 2, 'coach sees people for assigned companies via person_public');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000003","role":"authenticated"}', true);
select is((select count(*)::int from public.person_public), 0, 'ended helper sees no one via person_public');
reset role;

-- ---- Column proof: exactly the four safe columns, no contact, no demographic.
select columns_are(
  'public', 'person_public',
  array['id', 'company_id', 'display_name', 'role'],
  'person_public exposes only id, company_id, display_name, role');
select is(
  (select count(*)::int from information_schema.columns
    where table_schema='public' and table_name='person_public' and column_name in ('email','phone','first_name','last_name','demographics')),
  0, 'person_public exposes no contact or demographic column');

-- No view in public reads person_demographics.
select is(
  (select count(*)::int from information_schema.view_column_usage
    where view_schema='public' and table_name='person_demographics'),
  0, 'no public view selects from person_demographics');

-- A founder cannot reach person_demographics for their own company by any path.
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000006","role":"authenticated"}', true);
select is(
  (select count(*)::int from public.person_demographics d
     join public.company_person cp on cp.person_id = d.person_id
     where cp.company_id='22222222-0000-4000-8000-0000000000aa'),
  0, 'founder cannot join to demographics for their own company');
reset role;

select * from finish();
rollback;
