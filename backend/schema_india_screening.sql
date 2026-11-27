-- ============================================================
-- GlucoGuide India Screening (ICMR-INDIAB Model 3)
-- Run in Supabase SQL Editor AFTER schema.sql and schema_public_screening.sql
-- ============================================================

create table if not exists public.india_assessments (
  id             uuid primary key default gen_random_uuid(),
  user_id        uuid not null references auth.users(id) on delete cascade default auth.uid(),
  created_at     timestamptz not null default now(),
  model_family   text not null default 'india_indiab' check (model_family = 'india_indiab'),
  model_version  text not null,
  model_name     text not null,
  model_card_ref text not null default 'models/india_indiab/model_card.json',
  score          double precision not null check (score >= 0 and score <= 1),
  threshold      double precision not null check (threshold > 0 and threshold < 1),
  label          smallint not null check (label in (0, 1)),
  band           text not null check (band in ('higher', 'lower')),
  inputs         jsonb not null,
  missing_inputs jsonb not null default '[]'::jsonb,
  consent        boolean not null check (consent = true)
);

create index if not exists india_assessments_owner_created_idx
  on public.india_assessments (user_id, created_at desc);

alter table public.india_assessments enable row level security;
alter table public.india_assessments force row level security;
revoke all on public.india_assessments from anon;
grant select, insert, delete on public.india_assessments to authenticated;

drop policy if exists "owners read their india assessments" on public.india_assessments;
create policy "owners read their india assessments" on public.india_assessments
  for select to authenticated using ((select auth.uid()) = user_id);

drop policy if exists "owners create their india assessments" on public.india_assessments;
create policy "owners create their india assessments" on public.india_assessments
  for insert to authenticated with check ((select auth.uid()) = user_id);

drop policy if exists "owners delete their india assessments" on public.india_assessments;
create policy "owners delete their india assessments" on public.india_assessments
  for delete to authenticated using ((select auth.uid()) = user_id);
