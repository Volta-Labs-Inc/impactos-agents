-- The anonymous public reaches nothing: no table grant, no view grant, no
-- function execute. Default privileges are revoked and only `public` is exposed.
begin;
select plan(8);

set local role anon;
select throws_ok($$select count(*) from public.company$$,          '42501', NULL, 'anon cannot read company');
select throws_ok($$select count(*) from public.person$$,           '42501', NULL, 'anon cannot read person');
select throws_ok($$select count(*) from public.person_demographics$$,'42501', NULL, 'anon cannot read person_demographics');
select throws_ok($$select count(*) from public.person_public$$,     '42501', NULL, 'anon cannot read person_public');
select throws_ok($$select count(*) from public.app_role$$,          '42501', NULL, 'anon cannot read app_role');
select throws_ok($$select count(*) from public.submission$$,        '42501', NULL, 'anon cannot read submission');
select throws_ok($$select public.can_see_company('22222222-0000-4000-8000-0000000000aa')$$, '42501', NULL, 'anon cannot execute can_see_company');
select throws_ok($$select public.role_active('staff')$$,            '42501', NULL, 'anon cannot execute role_active');
reset role;

select * from finish();
rollback;
