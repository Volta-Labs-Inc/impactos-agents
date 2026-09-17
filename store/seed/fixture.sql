-- impactOS store fixture seed.
--
-- Six auth identities and a small estate that lets the pgTAP suite prove access
-- BOTH ways for every role: staff, an active helper, an ENDED helper (must see
-- nothing), a coach assigned to three companies, an advisor assigned to one, and
-- a founder of one company. Idempotent: safe to re-run.
--
-- Fixture passwords are known and live ONLY in this file (fixtures are disposable
-- and hold no real person's data). Every login is password grant "fixturepw".
-- All emails are @example.org so the repository PII scan stays green.

-- Fixed identifiers (documented so tests and docs can reference them):
--   staff          11111111-0000-4000-8000-000000000001
--   helper active  11111111-0000-4000-8000-000000000002
--   helper ended   11111111-0000-4000-8000-000000000003
--   coach          11111111-0000-4000-8000-000000000004  (companies A, B, C)
--   advisor        11111111-0000-4000-8000-000000000005  (company A)
--   founder        11111111-0000-4000-8000-000000000006  (company A)
--   company A 22222222-0000-4000-8000-0000000000aa
--   company B 22222222-0000-4000-8000-0000000000bb
--   company C 22222222-0000-4000-8000-0000000000cc
--   company D 22222222-0000-4000-8000-0000000000dd  (coach NOT assigned; denial case)

-- ---------------------------------------------------------------------------
-- auth.users (password grant enabled: confirmed email + bcrypt password).
-- ---------------------------------------------------------------------------
insert into auth.users (
  instance_id, id, aud, role, email, encrypted_password,
  email_confirmed_at, created_at, updated_at,
  raw_app_meta_data, raw_user_meta_data
)
values
  ('00000000-0000-0000-0000-000000000000', '11111111-0000-4000-8000-000000000001', 'authenticated', 'authenticated', 'staff@example.org',         extensions.crypt('fixturepw', extensions.gen_salt('bf')), now(), now(), now(), '{"provider":"email","providers":["email"]}', '{}'),
  ('00000000-0000-0000-0000-000000000000', '11111111-0000-4000-8000-000000000002', 'authenticated', 'authenticated', 'helper-active@example.org', extensions.crypt('fixturepw', extensions.gen_salt('bf')), now(), now(), now(), '{"provider":"email","providers":["email"]}', '{}'),
  ('00000000-0000-0000-0000-000000000000', '11111111-0000-4000-8000-000000000003', 'authenticated', 'authenticated', 'helper-ended@example.org',  extensions.crypt('fixturepw', extensions.gen_salt('bf')), now(), now(), now(), '{"provider":"email","providers":["email"]}', '{}'),
  ('00000000-0000-0000-0000-000000000000', '11111111-0000-4000-8000-000000000004', 'authenticated', 'authenticated', 'coach@example.org',         extensions.crypt('fixturepw', extensions.gen_salt('bf')), now(), now(), now(), '{"provider":"email","providers":["email"]}', '{}'),
  ('00000000-0000-0000-0000-000000000000', '11111111-0000-4000-8000-000000000005', 'authenticated', 'authenticated', 'advisor@example.org',       extensions.crypt('fixturepw', extensions.gen_salt('bf')), now(), now(), now(), '{"provider":"email","providers":["email"]}', '{}'),
  ('00000000-0000-0000-0000-000000000000', '11111111-0000-4000-8000-000000000006', 'authenticated', 'authenticated', 'founder@example.org',       extensions.crypt('fixturepw', extensions.gen_salt('bf')), now(), now(), now(), '{"provider":"email","providers":["email"]}', '{}')
on conflict (id) do nothing;

-- ---------------------------------------------------------------------------
-- app_user rows (display names only).
-- ---------------------------------------------------------------------------
insert into public.app_user (id, display_name) values
  ('11111111-0000-4000-8000-000000000001', 'Fixture Staff'),
  ('11111111-0000-4000-8000-000000000002', 'Fixture Helper (active)'),
  ('11111111-0000-4000-8000-000000000003', 'Fixture Helper (ended)'),
  ('11111111-0000-4000-8000-000000000004', 'Fixture Coach'),
  ('11111111-0000-4000-8000-000000000005', 'Fixture Advisor'),
  ('11111111-0000-4000-8000-000000000006', 'Fixture Founder')
on conflict (id) do nothing;

-- ---------------------------------------------------------------------------
-- user_role: the helper is time-bounded; the ended helper's window has passed.
-- ---------------------------------------------------------------------------
insert into public.user_role (user_id, role_id, starts_at, ends_at)
select u.uid, r.id, u.starts_at, u.ends_at
from (values
  ('11111111-0000-4000-8000-000000000001'::uuid, 'staff',   now() - interval '30 days', null::timestamptz),
  ('11111111-0000-4000-8000-000000000002'::uuid, 'helper',  now() - interval '30 days', now() + interval '365 days'),
  ('11111111-0000-4000-8000-000000000003'::uuid, 'helper',  now() - interval '60 days', now() - interval '1 day'),
  ('11111111-0000-4000-8000-000000000004'::uuid, 'coach',   now() - interval '30 days', null),
  ('11111111-0000-4000-8000-000000000005'::uuid, 'advisor', now() - interval '30 days', null),
  ('11111111-0000-4000-8000-000000000006'::uuid, 'founder', now() - interval '30 days', null)
) as u(uid, role_name, starts_at, ends_at)
join public.app_role r on r.name = u.role_name
on conflict (user_id, role_id) do nothing;

-- ---------------------------------------------------------------------------
-- The single organisation, and four companies.
-- ---------------------------------------------------------------------------
insert into public.organization (id, source_system, source_id, legal_name, operating_name, country)
values ('00000000-0000-0000-0000-000000000001', 'fixture', 'org-1', 'Fixture Incubator Inc.', 'Fixture Incubator', 'CA')
on conflict (id) do nothing;

insert into public.company (id, source_system, source_id, legal_name, operating_name, company_type, country) values
  ('22222222-0000-4000-8000-0000000000aa', 'fixture', 'company-a', 'Company A Ltd.', 'Company A', 'Startup', 'CA'),
  ('22222222-0000-4000-8000-0000000000bb', 'fixture', 'company-b', 'Company B Ltd.', 'Company B', 'Startup', 'CA'),
  ('22222222-0000-4000-8000-0000000000cc', 'fixture', 'company-c', 'Company C Ltd.', 'Company C', 'SME',     'CA'),
  ('22222222-0000-4000-8000-0000000000dd', 'fixture', 'company-d', 'Company D Ltd.', 'Company D', 'Startup', 'CA')
on conflict (source_system, source_id) do nothing;

-- ---------------------------------------------------------------------------
-- Assignments: coach -> A,B,C; advisor -> A; founder -> A.
-- ---------------------------------------------------------------------------
insert into public.company_assignment (user_id, company_id, role_id)
select a.uid, a.cid, r.id
from (values
  ('11111111-0000-4000-8000-000000000004'::uuid, '22222222-0000-4000-8000-0000000000aa'::uuid, 'coach'),
  ('11111111-0000-4000-8000-000000000004'::uuid, '22222222-0000-4000-8000-0000000000bb'::uuid, 'coach'),
  ('11111111-0000-4000-8000-000000000004'::uuid, '22222222-0000-4000-8000-0000000000cc'::uuid, 'coach'),
  ('11111111-0000-4000-8000-000000000005'::uuid, '22222222-0000-4000-8000-0000000000aa'::uuid, 'advisor'),
  ('11111111-0000-4000-8000-000000000006'::uuid, '22222222-0000-4000-8000-0000000000aa'::uuid, 'founder')
) as a(uid, cid, role_name)
join public.app_role r on r.name = a.role_name
on conflict (user_id, company_id, role_id) do nothing;

-- ---------------------------------------------------------------------------
-- People: one at A (with demographics), one at B, one at D.
-- ---------------------------------------------------------------------------
insert into public.person (id, source_system, source_id, first_name, last_name, email, phone, title) values
  ('33333333-0000-4000-8000-0000000000a1', 'fixture', 'person-a1', 'Ada',  'Alpha', 'ada.alpha@example.org',   '555-0142', 'CEO'),
  ('33333333-0000-4000-8000-0000000000b1', 'fixture', 'person-b1', 'Ben',  'Bravo', 'ben.bravo@example.org',   '555-0143', 'CTO'),
  ('33333333-0000-4000-8000-0000000000d1', 'fixture', 'person-d1', 'Dora', 'Delta', 'dora.delta@example.org',  '555-0144', 'CEO')
on conflict (source_system, source_id) do nothing;

insert into public.person_demographics (person_id, demographics)
values ('33333333-0000-4000-8000-0000000000a1', array['Women','Immigrants'])
on conflict (person_id) do nothing;

insert into public.company_person (source_system, source_id, company_id, person_id, role, is_primary) values
  ('fixture', 'cp-a1', '22222222-0000-4000-8000-0000000000aa', '33333333-0000-4000-8000-0000000000a1', 'Founder', true),
  ('fixture', 'cp-b1', '22222222-0000-4000-8000-0000000000bb', '33333333-0000-4000-8000-0000000000b1', 'Founder', true),
  ('fixture', 'cp-d1', '22222222-0000-4000-8000-0000000000dd', '33333333-0000-4000-8000-0000000000d1', 'Founder', true)
on conflict (source_system, source_id) do nothing;

-- ---------------------------------------------------------------------------
-- Programs, cohort, membership (company A enrolled).
-- ---------------------------------------------------------------------------
insert into public.program (source_system, source_id, name, program_type, status)
values ('fixture', 'program-1', 'Fixture Accelerator', 'Accelerator', 'Active')
on conflict (source_system, source_id) do nothing;

insert into public.cohort (source_system, source_id, program_id, cohort_name, start_date)
select 'fixture', 'cohort-1', p.id, 'Spring', date '2026-01-15'
from public.program p where p.source_system = 'fixture' and p.source_id = 'program-1'
on conflict (source_system, source_id) do nothing;

insert into public.membership (source_system, source_id, cohort_id, company_id, status)
select 'fixture', 'membership-a', c.id, '22222222-0000-4000-8000-0000000000aa', 'Active'
from public.cohort c where c.source_system = 'fixture' and c.source_id = 'cohort-1'
on conflict (source_system, source_id) do nothing;

-- ---------------------------------------------------------------------------
-- Company facts. Interaction only on A (founder must never see it).
-- ---------------------------------------------------------------------------
insert into public.interaction (source_system, source_id, interaction_type, occurred_at, company_id, subject, duration_hours) values
  ('fixture', 'interaction-a', 'coaching_session', date '2026-02-10', '22222222-0000-4000-8000-0000000000aa', 'Coaching session', 1.5)
on conflict (source_system, source_id) do nothing;

insert into public.interaction_participant (source_system, source_id, interaction_id, person_id, role)
select 'fixture', 'ip-a1', i.id, '33333333-0000-4000-8000-0000000000a1', 'attendee'
from public.interaction i where i.source_system = 'fixture' and i.source_id = 'interaction-a'
on conflict (source_system, source_id) do nothing;

insert into public.company_update (source_system, source_id, company_id, update_date, current_ftes, annual_revenue, annual_revenue_currency) values
  ('fixture', 'update-a', '22222222-0000-4000-8000-0000000000aa', date '2026-03-31', 5, 250000, 'CAD'),
  ('fixture', 'update-b', '22222222-0000-4000-8000-0000000000bb', date '2026-03-31', 3, 100000, 'CAD')
on conflict (source_system, source_id) do nothing;

insert into public.funding_event (source_system, source_id, company_id, funding_type, amount, amount_currency, close_date) values
  ('fixture', 'funding-a', '22222222-0000-4000-8000-0000000000aa', 'angel', 500000, 'CAD', date '2026-02-01')
on conflict (source_system, source_id) do nothing;

insert into public.team_member_period (source_system, source_id, company_id, person_id, period_month, hours_per_week, is_founder) values
  ('fixture', 'tmp-a1', '22222222-0000-4000-8000-0000000000aa', '33333333-0000-4000-8000-0000000000a1', '2026-03', 40, true)
on conflict (source_system, source_id) do nothing;

insert into public.milestone_position (source_system, source_id, company_id, track, rung_order, status, as_of_date) values
  ('fixture', 'mp-a', '22222222-0000-4000-8000-0000000000aa', 'software', 3, 'in_progress', date '2026-03-31')
on conflict (source_system, source_id) do nothing;

insert into public.milestone_target (source_system, source_id, company_id, track, target_rung_order, set_by, set_at) values
  ('fixture', 'mt-a', '22222222-0000-4000-8000-0000000000aa', 'software', 4, 'Fixture Coach', date '2026-03-31')
on conflict (source_system, source_id) do nothing;

-- ---------------------------------------------------------------------------
-- Submissions: two on A (founder's own), one on B (founder must not see).
-- ---------------------------------------------------------------------------
insert into public.submission (source_system, source_id, company_id, channel, submitted_at, status) values
  ('fixture', 'submission-a-pending',  '22222222-0000-4000-8000-0000000000aa', 'hosted_form', date '2026-03-20', 'pending'),
  ('fixture', 'submission-a-accepted', '22222222-0000-4000-8000-0000000000aa', 'skill',       date '2026-03-21', 'accepted'),
  ('fixture', 'submission-b-pending',  '22222222-0000-4000-8000-0000000000bb', 'hosted_form', date '2026-03-22', 'pending')
on conflict (source_system, source_id) do nothing;

-- ---------------------------------------------------------------------------
-- Provenance / bookkeeping. One row scoped to A, one staff-only (company null).
-- ---------------------------------------------------------------------------
insert into public.write_batch (id, company_id, created_by, note) values
  ('44444444-0000-4000-8000-0000000000a1', '22222222-0000-4000-8000-0000000000aa', '11111111-0000-4000-8000-000000000001', 'company A batch'),
  ('44444444-0000-4000-8000-000000000001', null,                                   '11111111-0000-4000-8000-000000000001', 'staff-only batch')
on conflict (id) do nothing;

insert into public.fact_provenance (source_system, source_id, fact_table, fact_id, company_id, write_batch_id) values
  ('fixture', 'prov-a',    'company_update', null, '22222222-0000-4000-8000-0000000000aa', '44444444-0000-4000-8000-0000000000a1'),
  ('fixture', 'prov-null', 'organization',   null, null,                                   '44444444-0000-4000-8000-000000000001')
on conflict (source_system, source_id) do nothing;

insert into public.retraction (company_id, fact_table, fact_id, reason, retracted_by) values
  ('22222222-0000-4000-8000-0000000000aa', 'company_update', null, 'superseded', '11111111-0000-4000-8000-000000000001')
on conflict do nothing;
