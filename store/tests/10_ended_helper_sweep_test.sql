-- One consolidated sweep: an ended helper (role window in the past) sees zero
-- rows on every data table. The only thing still visible is the app_role name
-- catalogue, which is the declared "authenticated read" audience and carries no
-- company, personal or financial data.
begin;
select plan(20);

set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000003","role":"authenticated"}', true);

select is((select count(*)::int from public.company),                0, 'ended helper: company = 0');
select is((select count(*)::int from public.company_assignment),     0, 'ended helper: company_assignment = 0');
select is((select count(*)::int from public.company_person),         0, 'ended helper: company_person = 0');
select is((select count(*)::int from public.organization),           0, 'ended helper: organization = 0');
select is((select count(*)::int from public.person),                 0, 'ended helper: person = 0');
select is((select count(*)::int from public.person_demographics),    0, 'ended helper: person_demographics = 0');
select is((select count(*)::int from public.person_public),          0, 'ended helper: person_public = 0');
select is((select count(*)::int from public.program),                0, 'ended helper: program = 0');
select is((select count(*)::int from public.cohort),                 0, 'ended helper: cohort = 0');
select is((select count(*)::int from public.membership),             0, 'ended helper: membership = 0');
select is((select count(*)::int from public.interaction),            0, 'ended helper: interaction = 0');
select is((select count(*)::int from public.interaction_participant),0, 'ended helper: interaction_participant = 0');
select is((select count(*)::int from public.company_update),         0, 'ended helper: company_update = 0');
select is((select count(*)::int from public.funding_event),          0, 'ended helper: funding_event = 0');
select is((select count(*)::int from public.team_member_period),     0, 'ended helper: team_member_period = 0');
select is((select count(*)::int from public.milestone_position),     0, 'ended helper: milestone_position = 0');
select is((select count(*)::int from public.milestone_target),       0, 'ended helper: milestone_target = 0');
select is((select count(*)::int from public.submission),             0, 'ended helper: submission = 0');
select is((select count(*)::int from public.fact_provenance),        0, 'ended helper: fact_provenance = 0');
select is((select count(*)::int from public.retraction),             0, 'ended helper: retraction = 0');

reset role;
select * from finish();
rollback;
