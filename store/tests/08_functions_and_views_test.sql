-- Function privileges and view security options. Every store function is revoked
-- from public and granted only to authenticated; the guard functions return false
-- for a null caller; every store view except person_public is security_invoker.
begin;
select plan(13);

-- anon can execute none of the store functions
select ok(not has_function_privilege('anon', 'app.uid()', 'EXECUTE'), 'anon cannot execute app.uid');
select ok(not has_function_privilege('anon', 'public.role_active(text)', 'EXECUTE'), 'anon cannot execute role_active');
select ok(not has_function_privilege('anon', 'public.can_see_company(uuid)', 'EXECUTE'), 'anon cannot execute can_see_company');

-- authenticated can execute all three
select ok(has_function_privilege('authenticated', 'app.uid()', 'EXECUTE'), 'authenticated can execute app.uid');
select ok(has_function_privilege('authenticated', 'public.role_active(text)', 'EXECUTE'), 'authenticated can execute role_active');
select ok(has_function_privilege('authenticated', 'public.can_see_company(uuid)', 'EXECUTE'), 'authenticated can execute can_see_company');

-- guard functions return false when the caller is null (no JWT subject)
set local role authenticated;
select set_config('request.jwt.claims', '{}', true);
select is(public.can_see_company('22222222-0000-4000-8000-0000000000aa'), false, 'can_see_company is false for a null caller');
select is(public.role_active('staff'), false, 'role_active is false for a null caller');
reset role;

-- the guard functions are reachable and correct for a real caller (coach)
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000004","role":"authenticated"}', true);
select is(public.can_see_company('22222222-0000-4000-8000-0000000000aa'), true,  'coach can_see_company true for an assigned company');
select is(public.can_see_company('22222222-0000-4000-8000-0000000000dd'), false, 'coach can_see_company false for an unassigned company');
reset role;

-- view security options (extension-owned views excluded)
select is(
  (select count(*)::int
     from pg_class c
     join pg_namespace n on n.oid = c.relnamespace
     where n.nspname = 'public' and c.relkind = 'v'
       and c.relname <> 'person_public'
       and not exists (select 1 from pg_depend d where d.objid = c.oid and d.deptype = 'e')
       and coalesce(array_to_string(c.reloptions, ','), '') not like '%security_invoker=true%'),
  0, 'every store view except person_public is security_invoker=true');
select ok(
  (select coalesce(array_to_string(c.reloptions, ','), '') not like '%security_invoker=true%'
     from pg_class c join pg_namespace n on n.oid = c.relnamespace
     where n.nspname = 'public' and c.relname = 'person_public'),
  'person_public is the single owner-run projection (not security_invoker)');

-- person_public must exist and be owner-run
select has_view('public', 'person_public', 'person_public view exists');

select * from finish();
rollback;
