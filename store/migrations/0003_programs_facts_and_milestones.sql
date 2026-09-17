-- impactOS store — migration 0003: programs, cohorts, memberships, interactions,
-- company facts, milestones, submissions and provenance. Forward-only, idempotent.
--
-- Audience summary (full table in docs/store.md):
--   program, cohort, milestone_track, milestone_definition -> staff/helper
--     read+write; coach, advisor and founder read.
--   membership, milestone_position, milestone_target, company_update,
--     funding_event, team_member_period -> staff/helper all; coach/advisor
--     (assigned); founder (own company).
--   interaction, interaction_participant -> staff/helper all; coach/advisor
--     (assigned); founder none.
--   submission -> founder inserts own pending rows and reads own rows;
--     staff/helper all commands; no founder update or delete.
--   fact_provenance, retraction, write_batch -> staff/helper all; coach, advisor
--     and founder read rows attached to a company they can otherwise see; only
--     staff/helper may insert a retraction.

-- ---------------------------------------------------------------------------
-- Programs, cohorts, memberships.
-- ---------------------------------------------------------------------------
create table if not exists public.program (
  id            uuid primary key default gen_random_uuid(),
  source_system text not null,
  source_id     text not null,
  name          text not null,
  description   text,
  program_type  text,
  start_date    date,
  end_date      date,
  status        text,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  unique (source_system, source_id)
);

create table if not exists public.cohort (
  id            uuid primary key default gen_random_uuid(),
  source_system text not null,
  source_id     text not null,
  program_id    uuid not null references public.program (id) on delete cascade,
  cohort_name   text,
  start_date    date not null,
  end_date      date,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  unique (source_system, source_id)
);

create table if not exists public.membership (
  id            uuid primary key default gen_random_uuid(),
  source_system text not null,
  source_id     text not null,
  cohort_id     uuid not null references public.cohort (id) on delete cascade,
  company_id    uuid not null references public.company (id) on delete cascade,
  status        text,
  start_date    date,
  end_date      date,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  unique (source_system, source_id)
);
create index if not exists membership_company_idx on public.membership (company_id);

-- ---------------------------------------------------------------------------
-- Interactions.
-- ---------------------------------------------------------------------------
create table if not exists public.interaction (
  id                uuid primary key default gen_random_uuid(),
  source_system     text not null,
  source_id         text not null,
  source_meeting_id text,
  interaction_type  text not null,
  occurred_at       date not null,
  company_id        uuid references public.company (id) on delete set null,
  subject           text,
  duration_hours    numeric,
  notes             text,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  unique (source_system, source_id)
);
create index if not exists interaction_company_idx on public.interaction (company_id);

create table if not exists public.interaction_participant (
  id             uuid primary key default gen_random_uuid(),
  source_system  text not null,
  source_id      text not null,
  interaction_id uuid not null references public.interaction (id) on delete cascade,
  person_id      uuid references public.person (id) on delete set null,
  role           text,
  created_at     timestamptz not null default now(),
  unique (source_system, source_id)
);
create index if not exists interaction_participant_interaction_idx on public.interaction_participant (interaction_id);

-- ---------------------------------------------------------------------------
-- Company facts (money as amount numeric + currency char(3)).
-- ---------------------------------------------------------------------------
create table if not exists public.company_update (
  id                       uuid primary key default gen_random_uuid(),
  source_system            text not null,
  source_id                text not null,
  company_id               uuid not null references public.company (id) on delete cascade,
  update_date              date not null,
  current_ftes             numeric,
  ft_employees_canada      integer,
  pt_employees_canada      integer,
  employees_outside_canada integer,
  annual_revenue           numeric,
  annual_revenue_currency  char(3),
  export_revenue           numeric,
  export_revenue_currency  char(3),
  lifetime_revenue         numeric,
  lifetime_revenue_currency char(3),
  revenue_disclosure       text,
  patents_applied          integer,
  patents_granted          integer,
  nps                      numeric,
  impact_rating            numeric,
  notes                    text,
  created_at               timestamptz not null default now(),
  updated_at               timestamptz not null default now(),
  unique (source_system, source_id)
);
create index if not exists company_update_company_idx on public.company_update (company_id);

create table if not exists public.funding_event (
  id                 uuid primary key default gen_random_uuid(),
  source_system      text not null,
  source_id          text not null,
  company_id         uuid not null references public.company (id) on delete cascade,
  funding_type       text not null,
  amount             numeric,
  amount_currency    char(3),
  source_name        text,
  close_date         date,
  round_name         text,
  grant_program_name text,
  is_active          boolean,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now(),
  unique (source_system, source_id)
);
create index if not exists funding_event_company_idx on public.funding_event (company_id);

create table if not exists public.team_member_period (
  id                uuid primary key default gen_random_uuid(),
  source_system     text not null,
  source_id         text not null,
  company_id        uuid not null references public.company (id) on delete cascade,
  person_id         uuid not null references public.person (id) on delete cascade,
  period_month      text not null,
  hours_per_week    numeric,
  is_founder        boolean,
  is_active         boolean,
  has_product_skill boolean,
  has_sales_skill   boolean,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  unique (source_system, source_id)
);
create index if not exists team_member_period_company_idx on public.team_member_period (company_id);

-- ---------------------------------------------------------------------------
-- Milestones. Tracks and their rungs are reference data (seeded from tracks.json
-- in store/seed/tracks.sql). Positions and targets are per company.
-- ---------------------------------------------------------------------------
create table if not exists public.milestone_track (
  id          uuid primary key default gen_random_uuid(),
  slug        text not null unique,
  name        text not null,
  description text,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create table if not exists public.milestone_definition (
  id                   uuid primary key default gen_random_uuid(),
  track_id             uuid not null references public.milestone_track (id) on delete cascade,
  rung_order           integer not null,
  name                 text not null,
  evidence_description text,
  objective_signal     text,
  funder_stage         text,
  created_at           timestamptz not null default now(),
  updated_at           timestamptz not null default now(),
  unique (track_id, rung_order)
);

create table if not exists public.milestone_position (
  id            uuid primary key default gen_random_uuid(),
  source_system text not null,
  source_id     text not null,
  company_id    uuid not null references public.company (id) on delete cascade,
  track         text not null,
  rung_order    integer not null,
  status        text,
  as_of_date    date not null,
  is_verified   boolean,
  notes         text,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  unique (source_system, source_id)
);
create index if not exists milestone_position_company_idx on public.milestone_position (company_id);

create table if not exists public.milestone_target (
  id                uuid primary key default gen_random_uuid(),
  source_system     text not null,
  source_id         text not null,
  company_id        uuid not null references public.company (id) on delete cascade,
  track             text not null,
  target_rung_order integer not null,
  objective_signal  text,
  set_by            text,
  set_at            date not null,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  unique (source_system, source_id)
);
create index if not exists milestone_target_company_idx on public.milestone_target (company_id);

-- ---------------------------------------------------------------------------
-- Submissions (founder inbox).
-- ---------------------------------------------------------------------------
create table if not exists public.submission (
  id                       uuid primary key default gen_random_uuid(),
  source_system            text not null,
  source_id                text not null,
  company_id               uuid references public.company (id) on delete set null,
  submitted_by_person_id   uuid references public.person (id) on delete set null,
  channel                  text not null,
  submitted_at             date not null,
  status                   text not null,
  confidence               numeric,
  raw_payload_ref          text,
  created_at               timestamptz not null default now(),
  updated_at               timestamptz not null default now(),
  unique (source_system, source_id)
);
create index if not exists submission_company_idx on public.submission (company_id);

-- ---------------------------------------------------------------------------
-- Provenance / write bookkeeping. company_id (nullable) is what scopes reads for
-- coach, advisor and founder; a null company_id row is staff/helper-only.
-- ---------------------------------------------------------------------------
create table if not exists public.write_batch (
  id         uuid primary key default gen_random_uuid(),
  company_id uuid references public.company (id) on delete set null,
  created_by uuid references auth.users (id) on delete set null,
  note       text,
  created_at timestamptz not null default now()
);

create table if not exists public.fact_provenance (
  id             uuid primary key default gen_random_uuid(),
  source_system  text not null,
  source_id      text not null,
  fact_table     text not null,
  fact_id        uuid,
  company_id     uuid references public.company (id) on delete set null,
  write_batch_id uuid references public.write_batch (id) on delete set null,
  recorded_at    timestamptz not null default now(),
  unique (source_system, source_id)
);
create index if not exists fact_provenance_company_idx on public.fact_provenance (company_id);

create table if not exists public.retraction (
  id           uuid primary key default gen_random_uuid(),
  company_id   uuid references public.company (id) on delete set null,
  fact_table   text not null,
  fact_id      uuid,
  reason       text,
  retracted_by uuid references auth.users (id) on delete set null,
  retracted_at timestamptz not null default now()
);
create index if not exists retraction_company_idx on public.retraction (company_id);

-- ---------------------------------------------------------------------------
-- RLS + grants.
-- ---------------------------------------------------------------------------
alter table public.program              enable row level security;
alter table public.cohort               enable row level security;
alter table public.membership           enable row level security;
alter table public.interaction          enable row level security;
alter table public.interaction_participant enable row level security;
alter table public.company_update       enable row level security;
alter table public.funding_event        enable row level security;
alter table public.team_member_period   enable row level security;
alter table public.milestone_track      enable row level security;
alter table public.milestone_definition enable row level security;
alter table public.milestone_position   enable row level security;
alter table public.milestone_target     enable row level security;
alter table public.submission           enable row level security;
alter table public.write_batch          enable row level security;
alter table public.fact_provenance      enable row level security;
alter table public.retraction           enable row level security;

grant select, insert, update, delete on public.program              to authenticated;
grant select, insert, update, delete on public.cohort               to authenticated;
grant select, insert, update, delete on public.membership           to authenticated;
grant select, insert, update, delete on public.interaction          to authenticated;
grant select, insert, update, delete on public.interaction_participant to authenticated;
grant select, insert, update, delete on public.company_update       to authenticated;
grant select, insert, update, delete on public.funding_event        to authenticated;
grant select, insert, update, delete on public.team_member_period   to authenticated;
grant select, insert, update, delete on public.milestone_track      to authenticated;
grant select, insert, update, delete on public.milestone_definition to authenticated;
grant select, insert, update, delete on public.milestone_position   to authenticated;
grant select, insert, update, delete on public.milestone_target     to authenticated;
grant select, insert, update, delete on public.submission           to authenticated;
grant select, insert, update, delete on public.write_batch          to authenticated;
grant select, insert, update, delete on public.fact_provenance      to authenticated;
grant select, insert, update, delete on public.retraction           to authenticated;

-- --- Reference tables read by every active role, written by staff/helper. ----
-- program
drop policy if exists program_select on public.program;
create policy program_select on public.program for select to authenticated
  using (public.role_active('staff') or public.role_active('helper')
      or public.role_active('coach') or public.role_active('advisor') or public.role_active('founder'));
drop policy if exists program_insert on public.program;
create policy program_insert on public.program for insert to authenticated
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists program_update on public.program;
create policy program_update on public.program for update to authenticated
  using (public.role_active('staff') or public.role_active('helper'))
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists program_delete on public.program;
create policy program_delete on public.program for delete to authenticated
  using (public.role_active('staff') or public.role_active('helper'));

-- cohort
drop policy if exists cohort_select on public.cohort;
create policy cohort_select on public.cohort for select to authenticated
  using (public.role_active('staff') or public.role_active('helper')
      or public.role_active('coach') or public.role_active('advisor') or public.role_active('founder'));
drop policy if exists cohort_insert on public.cohort;
create policy cohort_insert on public.cohort for insert to authenticated
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists cohort_update on public.cohort;
create policy cohort_update on public.cohort for update to authenticated
  using (public.role_active('staff') or public.role_active('helper'))
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists cohort_delete on public.cohort;
create policy cohort_delete on public.cohort for delete to authenticated
  using (public.role_active('staff') or public.role_active('helper'));

-- milestone_track
drop policy if exists milestone_track_select on public.milestone_track;
create policy milestone_track_select on public.milestone_track for select to authenticated
  using (public.role_active('staff') or public.role_active('helper')
      or public.role_active('coach') or public.role_active('advisor') or public.role_active('founder'));
drop policy if exists milestone_track_insert on public.milestone_track;
create policy milestone_track_insert on public.milestone_track for insert to authenticated
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists milestone_track_update on public.milestone_track;
create policy milestone_track_update on public.milestone_track for update to authenticated
  using (public.role_active('staff') or public.role_active('helper'))
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists milestone_track_delete on public.milestone_track;
create policy milestone_track_delete on public.milestone_track for delete to authenticated
  using (public.role_active('staff') or public.role_active('helper'));

-- milestone_definition
drop policy if exists milestone_definition_select on public.milestone_definition;
create policy milestone_definition_select on public.milestone_definition for select to authenticated
  using (public.role_active('staff') or public.role_active('helper')
      or public.role_active('coach') or public.role_active('advisor') or public.role_active('founder'));
drop policy if exists milestone_definition_insert on public.milestone_definition;
create policy milestone_definition_insert on public.milestone_definition for insert to authenticated
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists milestone_definition_update on public.milestone_definition;
create policy milestone_definition_update on public.milestone_definition for update to authenticated
  using (public.role_active('staff') or public.role_active('helper'))
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists milestone_definition_delete on public.milestone_definition;
create policy milestone_definition_delete on public.milestone_definition for delete to authenticated
  using (public.role_active('staff') or public.role_active('helper'));

-- --- Company-scoped tables: read via can_see_company, write staff/helper. -----
-- membership
drop policy if exists membership_select on public.membership;
create policy membership_select on public.membership for select to authenticated
  using (public.can_see_company(company_id));
drop policy if exists membership_insert on public.membership;
create policy membership_insert on public.membership for insert to authenticated
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists membership_update on public.membership;
create policy membership_update on public.membership for update to authenticated
  using (public.role_active('staff') or public.role_active('helper'))
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists membership_delete on public.membership;
create policy membership_delete on public.membership for delete to authenticated
  using (public.role_active('staff') or public.role_active('helper'));

-- company_update
drop policy if exists company_update_select on public.company_update;
create policy company_update_select on public.company_update for select to authenticated
  using (public.can_see_company(company_id));
drop policy if exists company_update_insert on public.company_update;
create policy company_update_insert on public.company_update for insert to authenticated
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists company_update_update on public.company_update;
create policy company_update_update on public.company_update for update to authenticated
  using (public.role_active('staff') or public.role_active('helper'))
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists company_update_delete on public.company_update;
create policy company_update_delete on public.company_update for delete to authenticated
  using (public.role_active('staff') or public.role_active('helper'));

-- funding_event
drop policy if exists funding_event_select on public.funding_event;
create policy funding_event_select on public.funding_event for select to authenticated
  using (public.can_see_company(company_id));
drop policy if exists funding_event_insert on public.funding_event;
create policy funding_event_insert on public.funding_event for insert to authenticated
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists funding_event_update on public.funding_event;
create policy funding_event_update on public.funding_event for update to authenticated
  using (public.role_active('staff') or public.role_active('helper'))
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists funding_event_delete on public.funding_event;
create policy funding_event_delete on public.funding_event for delete to authenticated
  using (public.role_active('staff') or public.role_active('helper'));

-- team_member_period
drop policy if exists team_member_period_select on public.team_member_period;
create policy team_member_period_select on public.team_member_period for select to authenticated
  using (public.can_see_company(company_id));
drop policy if exists team_member_period_insert on public.team_member_period;
create policy team_member_period_insert on public.team_member_period for insert to authenticated
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists team_member_period_update on public.team_member_period;
create policy team_member_period_update on public.team_member_period for update to authenticated
  using (public.role_active('staff') or public.role_active('helper'))
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists team_member_period_delete on public.team_member_period;
create policy team_member_period_delete on public.team_member_period for delete to authenticated
  using (public.role_active('staff') or public.role_active('helper'));

-- milestone_position
drop policy if exists milestone_position_select on public.milestone_position;
create policy milestone_position_select on public.milestone_position for select to authenticated
  using (public.can_see_company(company_id));
drop policy if exists milestone_position_insert on public.milestone_position;
create policy milestone_position_insert on public.milestone_position for insert to authenticated
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists milestone_position_update on public.milestone_position;
create policy milestone_position_update on public.milestone_position for update to authenticated
  using (public.role_active('staff') or public.role_active('helper'))
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists milestone_position_delete on public.milestone_position;
create policy milestone_position_delete on public.milestone_position for delete to authenticated
  using (public.role_active('staff') or public.role_active('helper'));

-- milestone_target
drop policy if exists milestone_target_select on public.milestone_target;
create policy milestone_target_select on public.milestone_target for select to authenticated
  using (public.can_see_company(company_id));
drop policy if exists milestone_target_insert on public.milestone_target;
create policy milestone_target_insert on public.milestone_target for insert to authenticated
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists milestone_target_update on public.milestone_target;
create policy milestone_target_update on public.milestone_target for update to authenticated
  using (public.role_active('staff') or public.role_active('helper'))
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists milestone_target_delete on public.milestone_target;
create policy milestone_target_delete on public.milestone_target for delete to authenticated
  using (public.role_active('staff') or public.role_active('helper'));

-- --- Interactions: staff/helper all; coach/advisor assigned; founder none. ----
drop policy if exists interaction_select on public.interaction;
create policy interaction_select on public.interaction for select to authenticated
  using (
    public.role_active('staff') or public.role_active('helper')
    or exists (
      select 1
      from public.company_assignment ca
      join public.app_role r on r.id = ca.role_id
      where ca.company_id = interaction.company_id
        and ca.user_id = app.uid()
        and r.name in ('coach', 'advisor')
        and ca.starts_at <= now() and (ca.ends_at is null or ca.ends_at > now())
    )
  );
drop policy if exists interaction_insert on public.interaction;
create policy interaction_insert on public.interaction for insert to authenticated
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists interaction_update on public.interaction;
create policy interaction_update on public.interaction for update to authenticated
  using (public.role_active('staff') or public.role_active('helper'))
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists interaction_delete on public.interaction;
create policy interaction_delete on public.interaction for delete to authenticated
  using (public.role_active('staff') or public.role_active('helper'));

drop policy if exists interaction_participant_select on public.interaction_participant;
create policy interaction_participant_select on public.interaction_participant for select to authenticated
  using (
    public.role_active('staff') or public.role_active('helper')
    or exists (
      select 1
      from public.interaction i
      join public.company_assignment ca on ca.company_id = i.company_id
      join public.app_role r on r.id = ca.role_id
      where i.id = interaction_participant.interaction_id
        and ca.user_id = app.uid()
        and r.name in ('coach', 'advisor')
        and ca.starts_at <= now() and (ca.ends_at is null or ca.ends_at > now())
    )
  );
drop policy if exists interaction_participant_insert on public.interaction_participant;
create policy interaction_participant_insert on public.interaction_participant for insert to authenticated
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists interaction_participant_update on public.interaction_participant;
create policy interaction_participant_update on public.interaction_participant for update to authenticated
  using (public.role_active('staff') or public.role_active('helper'))
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists interaction_participant_delete on public.interaction_participant;
create policy interaction_participant_delete on public.interaction_participant for delete to authenticated
  using (public.role_active('staff') or public.role_active('helper'));

-- --- Submissions: founder inserts own pending + reads own; staff/helper all. --
drop policy if exists submission_select on public.submission;
create policy submission_select on public.submission for select to authenticated
  using (
    public.role_active('staff') or public.role_active('helper')
    or (
      public.role_active('founder')
      and company_id is not null
      and exists (
        select 1
        from public.company_assignment ca
        join public.app_role r on r.id = ca.role_id
        where ca.company_id = submission.company_id
          and ca.user_id = app.uid()
          and r.name = 'founder'
          and ca.starts_at <= now() and (ca.ends_at is null or ca.ends_at > now())
      )
    )
  );
drop policy if exists submission_insert on public.submission;
create policy submission_insert on public.submission for insert to authenticated
  with check (
    public.role_active('staff') or public.role_active('helper')
    or (
      public.role_active('founder')
      and status = 'pending'
      and company_id is not null
      and exists (
        select 1
        from public.company_assignment ca
        join public.app_role r on r.id = ca.role_id
        where ca.company_id = submission.company_id
          and ca.user_id = app.uid()
          and r.name = 'founder'
          and ca.starts_at <= now() and (ca.ends_at is null or ca.ends_at > now())
      )
    )
  );
-- No founder update or delete: staff/helper only.
drop policy if exists submission_update on public.submission;
create policy submission_update on public.submission for update to authenticated
  using (public.role_active('staff') or public.role_active('helper'))
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists submission_delete on public.submission;
create policy submission_delete on public.submission for delete to authenticated
  using (public.role_active('staff') or public.role_active('helper'));

-- --- Provenance / write bookkeeping. -----------------------------------------
-- write_batch
drop policy if exists write_batch_select on public.write_batch;
create policy write_batch_select on public.write_batch for select to authenticated
  using (
    public.role_active('staff') or public.role_active('helper')
    or (company_id is not null and public.can_see_company(company_id))
  );
drop policy if exists write_batch_insert on public.write_batch;
create policy write_batch_insert on public.write_batch for insert to authenticated
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists write_batch_update on public.write_batch;
create policy write_batch_update on public.write_batch for update to authenticated
  using (public.role_active('staff') or public.role_active('helper'))
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists write_batch_delete on public.write_batch;
create policy write_batch_delete on public.write_batch for delete to authenticated
  using (public.role_active('staff') or public.role_active('helper'));

-- fact_provenance
drop policy if exists fact_provenance_select on public.fact_provenance;
create policy fact_provenance_select on public.fact_provenance for select to authenticated
  using (
    public.role_active('staff') or public.role_active('helper')
    or (company_id is not null and public.can_see_company(company_id))
  );
drop policy if exists fact_provenance_insert on public.fact_provenance;
create policy fact_provenance_insert on public.fact_provenance for insert to authenticated
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists fact_provenance_update on public.fact_provenance;
create policy fact_provenance_update on public.fact_provenance for update to authenticated
  using (public.role_active('staff') or public.role_active('helper'))
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists fact_provenance_delete on public.fact_provenance;
create policy fact_provenance_delete on public.fact_provenance for delete to authenticated
  using (public.role_active('staff') or public.role_active('helper'));

-- retraction: read like provenance; only staff/helper may insert (or change).
drop policy if exists retraction_select on public.retraction;
create policy retraction_select on public.retraction for select to authenticated
  using (
    public.role_active('staff') or public.role_active('helper')
    or (company_id is not null and public.can_see_company(company_id))
  );
drop policy if exists retraction_insert on public.retraction;
create policy retraction_insert on public.retraction for insert to authenticated
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists retraction_update on public.retraction;
create policy retraction_update on public.retraction for update to authenticated
  using (public.role_active('staff') or public.role_active('helper'))
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists retraction_delete on public.retraction;
create policy retraction_delete on public.retraction for delete to authenticated
  using (public.role_active('staff') or public.role_active('helper'));
