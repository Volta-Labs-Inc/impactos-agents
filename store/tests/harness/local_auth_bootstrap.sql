-- Test-harness ONLY. Not a production migration and never applied by
-- `impactos store provision`.
--
-- In a real Supabase project, GoTrue owns the `auth` schema and the `auth.users`
-- table, pgcrypto lives in `extensions`, and the anon/authenticated/service_role
-- roles are created by the platform. When the store schema is proven against a
-- bare database (an isolated database created inside a running Supabase Postgres
-- cluster), this file recreates the minimal subset the store's migrations and
-- fixture depend on, so the access proofs exercise the real policies. It creates
-- nothing the production migrations rely on beyond what the platform already
-- provides.

create schema if not exists extensions;
create extension if not exists pgcrypto with schema extensions;
create extension if not exists pgtap;

create schema if not exists auth;
grant usage on schema auth to anon, authenticated, service_role;

create table if not exists auth.users (
  instance_id        uuid,
  id                 uuid primary key,
  aud                varchar(255),
  role               varchar(255),
  email              varchar(255),
  encrypted_password varchar(255),
  email_confirmed_at timestamptz,
  created_at         timestamptz,
  updated_at         timestamptz,
  raw_app_meta_data  jsonb,
  raw_user_meta_data jsonb
);

-- Faithful to the platform definition (verified against a running Supabase 17
-- cluster): reads the request's JWT claims GUC set per statement in the tests.
create or replace function auth.uid()
returns uuid
language sql
stable
as $$
  select coalesce(
    nullif(current_setting('request.jwt.claim.sub', true), ''),
    (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub')
  )::uuid
$$;
grant execute on function auth.uid() to public;
