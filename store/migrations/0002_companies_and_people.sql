-- impactOS store — migration 0002: companies, assignments, people and the single
-- guarded company-visibility function. Forward-only and idempotent.
--
-- Audience summary (full table in docs/store.md):
--   company, company_update, funding_event, team_member_period, membership,
--   milestone_position, milestone_target, company_person  -> staff and active
--     helper (all); coach and advisor (assigned companies); founder (own company).
--   interaction, interaction_participant -> staff and active helper (all); coach
--     and advisor (assigned); founder none.
--   person -> staff and active helper (all); coach and advisor (persons linked to
--     assigned companies); founder none directly (only the person_public view).
--   person_demographics -> staff and active helper only.

-- ---------------------------------------------------------------------------
-- Companies.
-- ---------------------------------------------------------------------------
create table if not exists public.company (
  id                 uuid primary key default gen_random_uuid(),
  source_system      text not null,
  source_id          text not null,
  legal_name         text not null,
  operating_name     text,
  former_name        text,
  business_number    text,
  verified_domain    text,
  industry           text,
  company_type       text,
  city               text,
  province           text,
  country            text,
  website            text,
  year_incorporated  integer,
  year_of_first_sale integer,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now(),
  unique (source_system, source_id)
);

-- Which app users are attached to which company, and how. Coach and advisor
-- assignments scope their reads; a founder's own-company link lives here too.
create table if not exists public.company_assignment (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references auth.users (id) on delete cascade,
  company_id uuid not null references public.company (id) on delete cascade,
  role_id    uuid not null references public.app_role (id),
  starts_at  timestamptz not null default now(),
  ends_at    timestamptz,
  unique (user_id, company_id, role_id)
);
create index if not exists company_assignment_user_idx    on public.company_assignment (user_id);
create index if not exists company_assignment_company_idx on public.company_assignment (company_id);

-- ---------------------------------------------------------------------------
-- can_see_company(): may the caller see this company at all? Union of staff,
-- active helper, and any active company assignment (coach, advisor or founder).
-- Security definer + guarded + granted only to authenticated, exactly as
-- role_active. It is the only elevated function used by an owner-run view
-- (person_public) and gives SR-21 a yes/no answer the caller cannot fabricate
-- from an empty result set.
-- ---------------------------------------------------------------------------
create or replace function public.can_see_company(p_company_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select app.uid() is not null
     and (
       public.role_active('staff')
       or public.role_active('helper')
       or exists (
         select 1
         from public.company_assignment ca
         where ca.user_id = app.uid()
           and ca.company_id = p_company_id
           and ca.starts_at <= now()
           and (ca.ends_at is null or ca.ends_at > now())
       )
     )
$$;

revoke execute on function public.can_see_company(uuid) from public;
grant execute on function public.can_see_company(uuid) to authenticated;

alter table public.company            enable row level security;
alter table public.company_assignment enable row level security;

grant select, insert, update, delete on public.company to authenticated;
drop policy if exists company_select on public.company;
create policy company_select on public.company
  for select to authenticated
  using (public.can_see_company(id));
drop policy if exists company_write_insert on public.company;
create policy company_write_insert on public.company
  for insert to authenticated
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists company_write_update on public.company;
create policy company_write_update on public.company
  for update to authenticated
  using (public.role_active('staff') or public.role_active('helper'))
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists company_write_delete on public.company;
create policy company_write_delete on public.company
  for delete to authenticated
  using (public.role_active('staff') or public.role_active('helper'));

grant select, insert, update, delete on public.company_assignment to authenticated;
drop policy if exists company_assignment_select on public.company_assignment;
create policy company_assignment_select on public.company_assignment
  for select to authenticated
  using (user_id = app.uid() or public.role_active('staff') or public.role_active('helper'));
drop policy if exists company_assignment_insert on public.company_assignment;
create policy company_assignment_insert on public.company_assignment
  for insert to authenticated
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists company_assignment_update on public.company_assignment;
create policy company_assignment_update on public.company_assignment
  for update to authenticated
  using (public.role_active('staff') or public.role_active('helper'))
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists company_assignment_delete on public.company_assignment;
create policy company_assignment_delete on public.company_assignment
  for delete to authenticated
  using (public.role_active('staff') or public.role_active('helper'));

-- ---------------------------------------------------------------------------
-- Organisation (single row, enforced by a constant-id check).
-- ---------------------------------------------------------------------------
create table if not exists public.organization (
  id             uuid primary key default '00000000-0000-0000-0000-000000000001'
                   check (id = '00000000-0000-0000-0000-000000000001'),
  source_system  text not null,
  source_id      text not null,
  legal_name     text not null,
  operating_name text,
  website        text,
  country        text,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),
  unique (source_system, source_id)
);

alter table public.organization enable row level security;
grant select, insert, update, delete on public.organization to authenticated;
-- Staff and active helper read/write; coach, advisor and founder read.
drop policy if exists organization_select on public.organization;
create policy organization_select on public.organization
  for select to authenticated
  using (
    public.role_active('staff') or public.role_active('helper')
    or public.role_active('coach') or public.role_active('advisor')
    or public.role_active('founder')
  );
drop policy if exists organization_insert on public.organization;
create policy organization_insert on public.organization
  for insert to authenticated
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists organization_update on public.organization;
create policy organization_update on public.organization
  for update to authenticated
  using (public.role_active('staff') or public.role_active('helper'))
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists organization_delete on public.organization;
create policy organization_delete on public.organization
  for delete to authenticated
  using (public.role_active('staff') or public.role_active('helper'));

-- ---------------------------------------------------------------------------
-- People. Personal contact columns live here (seen by staff, helper, and the
-- coach/advisor linked to the person's company). Demographics are split out.
-- ---------------------------------------------------------------------------
create table if not exists public.person (
  id            uuid primary key default gen_random_uuid(),
  source_system text not null,
  source_id     text not null,
  first_name    text,
  last_name     text,
  email         text,
  phone         text,
  title         text,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  unique (source_system, source_id)
);

-- Self-identified diverse-group membership (PacifiCan list). Kept in its own
-- table so no policy on person, and no export view, can ever surface it to a
-- coach, advisor or founder (D-18).
create table if not exists public.person_demographics (
  id           uuid primary key default gen_random_uuid(),
  person_id    uuid not null unique references public.person (id) on delete cascade,
  demographics text[] not null default '{}',
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);

-- The single company<->person join: role and tenure.
create table if not exists public.company_person (
  id            uuid primary key default gen_random_uuid(),
  source_system text not null,
  source_id     text not null,
  company_id    uuid not null references public.company (id) on delete cascade,
  person_id     uuid not null references public.person (id) on delete cascade,
  role          text,
  is_primary    boolean,
  start_date    date,
  end_date      date,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  unique (source_system, source_id)
);
create index if not exists company_person_company_idx on public.company_person (company_id);
create index if not exists company_person_person_idx  on public.company_person (person_id);

alter table public.person              enable row level security;
alter table public.person_demographics enable row level security;
alter table public.company_person      enable row level security;

grant select, insert, update, delete on public.person to authenticated;
-- Staff/helper see everyone; a coach or advisor sees a person only through an
-- active assignment to one of that person's companies. Founders: no policy here.
drop policy if exists person_select on public.person;
create policy person_select on public.person
  for select to authenticated
  using (
    public.role_active('staff') or public.role_active('helper')
    or exists (
      select 1
      from public.company_person cp
      join public.company_assignment ca on ca.company_id = cp.company_id
      join public.app_role r on r.id = ca.role_id
      where cp.person_id = person.id
        and ca.user_id = app.uid()
        and r.name in ('coach', 'advisor')
        and ca.starts_at <= now()
        and (ca.ends_at is null or ca.ends_at > now())
    )
  );
drop policy if exists person_insert on public.person;
create policy person_insert on public.person
  for insert to authenticated
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists person_update on public.person;
create policy person_update on public.person
  for update to authenticated
  using (public.role_active('staff') or public.role_active('helper'))
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists person_delete on public.person;
create policy person_delete on public.person
  for delete to authenticated
  using (public.role_active('staff') or public.role_active('helper'));

grant select, insert, update, delete on public.person_demographics to authenticated;
-- Staff and active helper only — for every command.
drop policy if exists person_demographics_select on public.person_demographics;
create policy person_demographics_select on public.person_demographics
  for select to authenticated
  using (public.role_active('staff') or public.role_active('helper'));
drop policy if exists person_demographics_insert on public.person_demographics;
create policy person_demographics_insert on public.person_demographics
  for insert to authenticated
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists person_demographics_update on public.person_demographics;
create policy person_demographics_update on public.person_demographics
  for update to authenticated
  using (public.role_active('staff') or public.role_active('helper'))
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists person_demographics_delete on public.person_demographics;
create policy person_demographics_delete on public.person_demographics
  for delete to authenticated
  using (public.role_active('staff') or public.role_active('helper'));

grant select, insert, update, delete on public.company_person to authenticated;
-- Each user reads the join rows for a company they can see; staff/helper write all.
drop policy if exists company_person_select on public.company_person;
create policy company_person_select on public.company_person
  for select to authenticated
  using (public.can_see_company(company_id));
drop policy if exists company_person_insert on public.company_person;
create policy company_person_insert on public.company_person
  for insert to authenticated
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists company_person_update on public.company_person;
create policy company_person_update on public.company_person
  for update to authenticated
  using (public.role_active('staff') or public.role_active('helper'))
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists company_person_delete on public.company_person;
create policy company_person_delete on public.company_person
  for delete to authenticated
  using (public.role_active('staff') or public.role_active('helper'));

-- ---------------------------------------------------------------------------
-- person_public: the ONLY projection a founder uses to see people, and the only
-- owner-run view in the store. It runs as its owner (security_invoker NOT set) so
-- it can read person past that table's RLS, but every row is gated by
-- can_see_company, so a founder sees exactly the display name and role of people
-- at their own company and nothing else. Column list is deliberately minimal:
-- id, company_id, display_name, role — no contact details, no demographics.
-- ---------------------------------------------------------------------------
drop view if exists public.person_public;
create view public.person_public as
  select
    p.id,
    cp.company_id,
    nullif(btrim(concat_ws(' ', p.first_name, p.last_name)), '') as display_name,
    cp.role
  from public.person p
  join public.company_person cp on cp.person_id = p.id
  where public.can_see_company(cp.company_id);

grant select on public.person_public to authenticated;
