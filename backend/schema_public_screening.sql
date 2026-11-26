-- ============================================================
-- GlucoGuide Public Screening — additional tables
-- Run this in your Supabase SQL Editor AFTER the base schema.sql
-- ============================================================

-- Public screening assessments (Model 2 — NHANES public model)
-- Completely separate from the existing Pima `assessments` table.
create table if not exists public.screening_assessments (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references auth.users(id) on delete cascade default auth.uid(),
  created_at    timestamptz not null default now(),
  model_version text not null,
  model_name    text not null,
  model_type    text not null default 'public_screening',
  score         double precision not null check (score >= 0 and score <= 1),
  label         smallint not null check (label in (0, 1)),
  band          text not null check (band in ('higher', 'lower')),
  threshold     double precision not null check (threshold > 0 and threshold < 1),
  -- Stored inputs — physical measurements only, no lab values
  inputs        jsonb not null,
  missing_inputs jsonb not null default '[]'::jsonb,
  dataset       text not null default 'NHANES 2017-2018'
);

create index if not exists screening_assessments_owner_created_idx
  on public.screening_assessments (user_id, created_at desc);

alter table public.screening_assessments enable row level security;
alter table public.screening_assessments force row level security;
revoke all on public.screening_assessments from anon;
grant select, insert, delete on public.screening_assessments to authenticated;

drop policy if exists "owners read their screening assessments" on public.screening_assessments;
create policy "owners read their screening assessments" on public.screening_assessments
  for select to authenticated using ((select auth.uid()) = user_id);

drop policy if exists "owners create their screening assessments" on public.screening_assessments;
create policy "owners create their screening assessments" on public.screening_assessments
  for insert to authenticated with check ((select auth.uid()) = user_id);

drop policy if exists "owners delete their screening assessments" on public.screening_assessments;
create policy "owners delete their screening assessments" on public.screening_assessments
  for delete to authenticated using ((select auth.uid()) = user_id);
