-- impactOS store — migration 0004 (child 6b): the write path, the founder
-- acceptance queue and its rules. Forward-only and idempotent.
--
-- This migration ADDS to the 6a schema; it changes no 6a table, policy or
-- function. Everything here supports writing facts under the signed-in user's
-- session, the guarded founder-submission acceptance, and the seeded acceptance
-- rules.
--
-- New objects:
--   * public.acceptance_rule            -- field-class -> route (seeded from the
--                                          contract's default policy; adopters may
--                                          override per deployment).
--   * app._insert_fact(text,jsonb,uuid) -- one whitelisted, dynamic fact insert.
--   * public.apply_write_batch(...)     -- one atomic, idempotent batch write; runs
--                                          as the caller, so 6a RLS still decides
--                                          what may be written (staff/helper).
--   * public.accept_submission(uuid)    -- the ONLY door a founder submission takes
--                                          to become facts; security definer, reads
--                                          acceptance_rule, refuses review classes
--                                          to a founder, attributes the founder as
--                                          source.
--
-- The founder never writes a fact table directly (6a denies it); the founder's
-- own writes are limited to a `pending` submission (6a). The structured proposal
-- travels in submission.raw_payload_ref as JSON: {"fields":[{field_class,
-- fact_table, record{...}}]}. No new founder-writable table is introduced.

-- ---------------------------------------------------------------------------
-- Acceptance rules. One row per field class; the route decides whether a
-- founder-submitted value of that class is auto-accepted or held for a person.
-- Seeded from contract/acceptance-rules.json (D-17); kept in sync by
-- tests/test_acceptance_rules.py. Read by every active role; written by
-- staff/helper only.
-- ---------------------------------------------------------------------------
create table if not exists public.acceptance_rule (
  field_class text primary key,
  route       text not null check (route in ('auto_accept', 'review', 'reject')),
  rationale   text,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

alter table public.acceptance_rule enable row level security;
grant select, insert, update, delete on public.acceptance_rule to authenticated;

drop policy if exists acceptance_rule_select on public.acceptance_rule;
create policy acceptance_rule_select on public.acceptance_rule for select to authenticated
  using (public.role_active('staff') or public.role_active('helper')
      or public.role_active('coach') or public.role_active('advisor') or public.role_active('founder'));
drop policy if exists acceptance_rule_insert on public.acceptance_rule;
create policy acceptance_rule_insert on public.acceptance_rule for insert to authenticated
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists acceptance_rule_update on public.acceptance_rule;
create policy acceptance_rule_update on public.acceptance_rule for update to authenticated
  using (public.role_active('staff') or public.role_active('helper'))
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists acceptance_rule_delete on public.acceptance_rule;
create policy acceptance_rule_delete on public.acceptance_rule for delete to authenticated
  using (public.role_active('staff') or public.role_active('helper'));

-- Default policy (contract/acceptance-rules.json, D-17). Idempotent: an adopter
-- may change a route afterwards and re-provisioning will not overwrite it.
insert into public.acceptance_rule (field_class, route, rationale) values
  ('identifier',  'auto_accept', 'Source identifiers are structural, not judgement calls.'),
  ('descriptive', 'auto_accept', 'Names and labels are low-risk; corrections are cheap.'),
  ('operational', 'auto_accept', 'Dates, statuses and references are structural.'),
  ('metric',      'auto_accept', 'Metrics such as employee counts and revenue figures are auto-accepted (D-17).'),
  ('financial',   'review',      'Funding and financial amounts are reviewed before they are applied (D-17).'),
  ('personal',    'review',      'Personal contact details are reviewed to avoid mis-association.'),
  ('demographic', 'review',      'Demographics are never inferred and are reviewed before applying (D-17, D-18).'),
  ('stage',       'review',      'Milestone and stage positions are reviewed before they are applied (D-17).')
on conflict (field_class) do nothing;

-- ---------------------------------------------------------------------------
-- app._insert_fact: the single dynamic insert used by both the batch write path
-- and the acceptance function. It refuses any table outside the fact whitelist,
-- so neither path can be steered into a privilege table (app_role, user_role,
-- company_assignment, …) even when it runs as the definer in accept_submission.
-- It always stamps a fresh id, the caller-supplied company_id, and the row
-- timestamps, so a proposed record can never set its own primary key or attach a
-- fact to another company.
--
-- SECURITY INVOKER: when apply_write_batch (invoker) calls it, 6a RLS decides
-- what may be written; when accept_submission (definer) calls it, the effective
-- user is the function owner, so the guarded acceptance can write on the
-- founder's behalf. The whitelist is what keeps that power narrow.
-- ---------------------------------------------------------------------------
create or replace function app._insert_fact(p_table text, p_record jsonb, p_company_id uuid)
returns uuid
language plpgsql
volatile
security invoker
set search_path = public
as $$
declare
  v_id  uuid := gen_random_uuid();
  v_rec jsonb;
begin
  if p_table not in (
    'company_update', 'funding_event', 'team_member_period',
    'milestone_position', 'milestone_target', 'interaction', 'membership'
  ) then
    raise exception 'fact table % is not writable through the store write path', p_table
      using errcode = '42501';
  end if;
  v_rec := coalesce(p_record, '{}'::jsonb)
           || jsonb_build_object(
                'id', v_id,
                'company_id', p_company_id,
                'created_at', now(),
                'updated_at', now());
  execute format(
    'insert into public.%I select * from jsonb_populate_record(null::public.%I, $1)',
    p_table, p_table) using v_rec;
  return v_id;
end;
$$;

revoke execute on function app._insert_fact(text, jsonb, uuid) from public;
grant execute on function app._insert_fact(text, jsonb, uuid) to authenticated;

-- ---------------------------------------------------------------------------
-- apply_write_batch: one atomic, idempotent batch write. The batch id is the
-- request hash (mapped to a uuid by the CLI), so the FIRST thing the function
-- does is claim it; if the id already exists the whole call is a no-op and no
-- fact is written twice. SECURITY INVOKER, so 6a's write_batch/fact policies
-- (staff/helper) decide whether the caller may write at all — a founder calling
-- this fails at the write_batch insert and the transaction rolls back.
--
-- p_facts is an array of {"fact_table":..., "record":{...},
-- "provenance":{"source_system":..., "source_id":...}}.
-- ---------------------------------------------------------------------------
create or replace function public.apply_write_batch(
  p_batch_id   uuid,
  p_company_id uuid,
  p_note       text,
  p_facts      jsonb)
returns jsonb
language plpgsql
volatile
security invoker
set search_path = public
as $$
declare
  v_inserted int;
  v_fact     jsonb;
  v_fact_id  uuid;
  v_company  uuid;
  v_count    int := 0;
begin
  insert into public.write_batch (id, company_id, created_by, note)
  values (p_batch_id, p_company_id, app.uid(), p_note)
  on conflict (id) do nothing;
  get diagnostics v_inserted = row_count;
  if v_inserted = 0 then
    return jsonb_build_object('status', 'noop', 'batch_id', p_batch_id, 'fact_count', 0);
  end if;

  for v_fact in select value from jsonb_array_elements(coalesce(p_facts, '[]'::jsonb)) as t(value)
  loop
    v_company := coalesce(nullif(v_fact->'record'->>'company_id', '')::uuid, p_company_id);
    v_fact_id := app._insert_fact(v_fact->>'fact_table', v_fact->'record', v_company);
    insert into public.fact_provenance
      (source_system, source_id, fact_table, fact_id, company_id, write_batch_id)
    values (
      coalesce(v_fact->'provenance'->>'source_system', v_fact->'record'->>'source_system', 'store'),
      coalesce(v_fact->'provenance'->>'source_id',
               v_fact->'record'->>'source_id',
               p_batch_id::text || ':' || v_count::text),
      v_fact->>'fact_table', v_fact_id, v_company, p_batch_id);
    v_count := v_count + 1;
  end loop;

  return jsonb_build_object('status', 'applied', 'batch_id', p_batch_id, 'fact_count', v_count);
end;
$$;

revoke execute on function public.apply_write_batch(uuid, uuid, text, jsonb) from public;
grant execute on function public.apply_write_batch(uuid, uuid, text, jsonb) to authenticated;

-- ---------------------------------------------------------------------------
-- accept_submission: the only path a founder submission takes to become facts.
-- SECURITY DEFINER + set search_path = public, revoked from public and granted
-- only to authenticated. It:
--   * refuses anything but a `pending` submission;
--   * lets the submitting founder act ONLY when every proposed field class routes
--     to auto_accept; any review class needs staff or an active helper; any reject
--     class is refused outright;
--   * refuses a caller who is neither staff/helper nor the submission's own
--     founder (so a founder cannot act on another company's submission);
--   * writes the facts with the founder recorded as the source, and marks the
--     submission accepted.
-- Because it is definer, it can write the fact tables a founder cannot; the fact
-- whitelist in app._insert_fact keeps that power to fact tables only.
-- ---------------------------------------------------------------------------
create or replace function public.accept_submission(p_submission_id uuid)
returns jsonb
language plpgsql
volatile
security definer
set search_path = public
as $$
declare
  v_uid          uuid := app.uid();
  v_sub          public.submission;
  v_is_staff     boolean;
  v_is_founder   boolean;
  v_founder_uid  uuid;
  v_fields       jsonb;
  v_field        jsonb;
  v_route        text;
  v_needs_review boolean := false;
  v_batch_id     uuid := gen_random_uuid();
  v_fact_id      uuid;
  v_count        int := 0;
begin
  if v_uid is null then
    raise exception 'not authenticated' using errcode = '42501';
  end if;

  select * into v_sub from public.submission where id = p_submission_id;
  if not found then
    raise exception 'submission % not found', p_submission_id using errcode = 'P0002';
  end if;
  if v_sub.status <> 'pending' then
    raise exception 'submission % is not pending (status %)', p_submission_id, v_sub.status
      using errcode = '42501';
  end if;

  v_is_staff := public.role_active('staff') or public.role_active('helper');
  v_is_founder := exists (
    select 1
    from public.company_assignment ca
    join public.app_role r on r.id = ca.role_id
    where ca.user_id = v_uid
      and ca.company_id = v_sub.company_id
      and r.name = 'founder'
      and ca.starts_at <= now() and (ca.ends_at is null or ca.ends_at > now())
  );

  if not (v_is_staff or v_is_founder) then
    raise exception 'not authorised to act on submission %', p_submission_id using errcode = '42501';
  end if;

  v_fields := coalesce(nullif(v_sub.raw_payload_ref, '')::jsonb -> 'fields', '[]'::jsonb);

  for v_field in select value from jsonb_array_elements(v_fields) as t(value)
  loop
    select route into v_route from public.acceptance_rule
      where field_class = v_field->>'field_class';
    v_route := coalesce(v_route, 'review');  -- an unknown class is conservative.
    if v_route = 'reject' then
      raise exception 'submission % contains a rejected field class %',
        p_submission_id, v_field->>'field_class' using errcode = '42501';
    elsif v_route = 'review' then
      v_needs_review := true;
    end if;
  end loop;

  if v_needs_review and not v_is_staff then
    raise exception 'submission % needs staff review before it can be accepted', p_submission_id
      using errcode = '42501';
  end if;

  -- The founder of the submission's company is the source of record.
  select ca.user_id into v_founder_uid
  from public.company_assignment ca
  join public.app_role r on r.id = ca.role_id
  where ca.company_id = v_sub.company_id
    and r.name = 'founder'
    and ca.starts_at <= now() and (ca.ends_at is null or ca.ends_at > now())
  order by ca.starts_at
  limit 1;

  insert into public.write_batch (id, company_id, created_by, note)
  values (v_batch_id, v_sub.company_id, coalesce(v_founder_uid, v_uid),
          'founder submission ' || coalesce(v_sub.source_id, p_submission_id::text));

  for v_field in select value from jsonb_array_elements(v_fields) as t(value)
  loop
    v_fact_id := app._insert_fact(v_field->>'fact_table', v_field->'record', v_sub.company_id);
    insert into public.fact_provenance
      (source_system, source_id, fact_table, fact_id, company_id, write_batch_id)
    values ('founder_submission',
            coalesce(v_sub.source_id, p_submission_id::text) || ':' || v_count::text,
            v_field->>'fact_table', v_fact_id, v_sub.company_id, v_batch_id);
    v_count := v_count + 1;
  end loop;

  update public.submission set status = 'accepted', updated_at = now()
  where id = p_submission_id;

  return jsonb_build_object('status', 'accepted', 'submission_id', p_submission_id,
                            'batch_id', v_batch_id, 'fact_count', v_count);
end;
$$;

revoke execute on function public.accept_submission(uuid) from public;
grant execute on function public.accept_submission(uuid) to authenticated;
