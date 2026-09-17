-- impactOS store — migration 0001: roles, users and the time-bounded helper.
--
-- Forward-only and idempotent. Applied in order by `impactos store provision`
-- through the Supabase management API SQL endpoint, authenticated with the
-- operator's personal access token (kept in the OS keychain by `supabase login`).
-- No service-role key and no database password are ever held, passed or written.
--
-- Consumers of this database (recorded in docs/store.md): the `impactos` CLI and
-- the child-6b founder shim, both authenticating as the signed-in user. No other
-- app, job, edge function or service reads or writes this project.
--
-- Access model (see docs/store.md for the full audience table):
--   * only the `public` schema is exposed through the Data API, so every
--     REST-callable function lives in `public`; the internal `app` schema is not
--     exposed and holds `app.uid()`.
--   * default privileges revoke all table access from anon and authenticated;
--     each table is then granted exactly the commands its policies require.
--   * every table has RLS enabled with plain EXISTS policies keyed on the
--     caller's active roles. Time-bounded roles (the helper) stop granting access
--     the instant `user_role.ends_at` passes.

-- ---------------------------------------------------------------------------
-- Internal schema and the caller-identity accessor.
-- ---------------------------------------------------------------------------
create schema if not exists app;

-- New public tables and functions must not be reachable by the anonymous or the
-- generic authenticated role by default; we grant back explicitly, per object.
alter default privileges in schema public revoke all on tables from anon, authenticated;
alter default privileges in schema public revoke execute on functions from public, anon, authenticated;
alter default privileges in schema app revoke all on tables from anon, authenticated;
alter default privileges in schema app revoke execute on functions from public, anon, authenticated;

-- app.uid(): the caller's auth user id. Internal (schema `app` is not exposed via
-- the API), security invoker, and readable only by authenticated sessions.
create or replace function app.uid()
returns uuid
language sql
stable
security invoker
as $$
  select auth.uid()
$$;

revoke execute on function app.uid() from public;
grant usage on schema app to authenticated;
grant execute on function app.uid() to authenticated;

-- ---------------------------------------------------------------------------
-- Role catalogue and user/role assignments.
-- ---------------------------------------------------------------------------
create table if not exists public.app_role (
  id   uuid primary key default gen_random_uuid(),
  name text not null unique
);

-- The five system roles, resolved by name (no hardcoded UUIDs anywhere else).
insert into public.app_role (name)
values ('staff'), ('coach'), ('advisor'), ('founder'), ('helper')
on conflict (name) do nothing;

create table if not exists public.app_user (
  id           uuid primary key references auth.users (id) on delete cascade,
  display_name text,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);

-- A user holds a role from starts_at until ends_at (nullable = open-ended). The
-- helper is the only role deployments time-box today; the column applies to any
-- role. `ends_at > now()` is the single freshness test used everywhere.
create table if not exists public.user_role (
  id        uuid primary key default gen_random_uuid(),
  user_id   uuid not null references auth.users (id) on delete cascade,
  role_id   uuid not null references public.app_role (id),
  starts_at timestamptz not null default now(),
  ends_at   timestamptz,
  unique (user_id, role_id)
);

create index if not exists user_role_user_idx on public.user_role (user_id);

-- ---------------------------------------------------------------------------
-- role_active(): does the caller hold this role right now? Security definer so it
-- can read user_role without tripping that table's own RLS (which would recurse),
-- guarded so a null caller (anon) always gets false, and callable only by
-- authenticated sessions. It answers a question about the caller alone, never
-- returning another user's data, so definer is safe here.
-- ---------------------------------------------------------------------------
create or replace function public.role_active(role_name text)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select app.uid() is not null
     and exists (
       select 1
       from public.user_role ur
       join public.app_role r on r.id = ur.role_id
       where ur.user_id = app.uid()
         and r.name = role_name
         and ur.starts_at <= now()
         and (ur.ends_at is null or ur.ends_at > now())
     )
$$;

revoke execute on function public.role_active(text) from public;
grant execute on function public.role_active(text) to authenticated;

-- ---------------------------------------------------------------------------
-- RLS + grants for the role tables.
-- ---------------------------------------------------------------------------
alter table public.app_role  enable row level security;
alter table public.app_user  enable row level security;
alter table public.user_role enable row level security;

-- app_role: any authenticated user may read the role names; nobody writes through
-- the API (seeded here, in the migration, as the table owner).
grant select on public.app_role to authenticated;
drop policy if exists app_role_read on public.app_role;
create policy app_role_read on public.app_role
  for select to authenticated using (true);

-- app_user: a user reads their own row; staff and active helper read and write all.
grant select, insert, update, delete on public.app_user to authenticated;
drop policy if exists app_user_select on public.app_user;
create policy app_user_select on public.app_user
  for select to authenticated
  using (id = app.uid() or public.role_active('staff') or public.role_active('helper'));
drop policy if exists app_user_insert on public.app_user;
create policy app_user_insert on public.app_user
  for insert to authenticated
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists app_user_update on public.app_user;
create policy app_user_update on public.app_user
  for update to authenticated
  using (public.role_active('staff') or public.role_active('helper'))
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists app_user_delete on public.app_user;
create policy app_user_delete on public.app_user
  for delete to authenticated
  using (public.role_active('staff') or public.role_active('helper'));

-- user_role: a user reads their own role rows; staff and active helper read and
-- write all (this is how a helper is ended — staff/helper set ends_at).
grant select, insert, update, delete on public.user_role to authenticated;
drop policy if exists user_role_select on public.user_role;
create policy user_role_select on public.user_role
  for select to authenticated
  using (user_id = app.uid() or public.role_active('staff') or public.role_active('helper'));
drop policy if exists user_role_insert on public.user_role;
create policy user_role_insert on public.user_role
  for insert to authenticated
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists user_role_update on public.user_role;
create policy user_role_update on public.user_role
  for update to authenticated
  using (public.role_active('staff') or public.role_active('helper'))
  with check (public.role_active('staff') or public.role_active('helper'));
drop policy if exists user_role_delete on public.user_role;
create policy user_role_delete on public.user_role
  for delete to authenticated
  using (public.role_active('staff') or public.role_active('helper'));
