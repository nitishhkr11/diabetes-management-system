-- Run in the Supabase SQL Editor. RLS is the final owner boundary; the API
-- forwards each verified user's JWT and never uses a service-role secret.
create table if not exists public.assessments (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade default auth.uid(),
  created_at timestamptz not null default now(),
  model_version text not null,
  model_name text not null check (model_name in ('Logistic Regression', 'Gaussian Naive Bayes', 'Random Forest')),
  score double precision not null check (score >= 0 and score <= 1),
  label smallint not null check (label in (0, 1)),
  threshold double precision not null check (threshold > 0 and threshold < 1),
  inputs jsonb not null,
  explanation jsonb not null
);

create index if not exists assessments_owner_created_idx
  on public.assessments (user_id, created_at desc);

alter table public.assessments enable row level security;
alter table public.assessments force row level security;
revoke all on public.assessments from anon;
grant select, insert, delete on public.assessments to authenticated;

drop policy if exists "owners read their assessments" on public.assessments;
create policy "owners read their assessments" on public.assessments
  for select to authenticated using ((select auth.uid()) = user_id);

drop policy if exists "owners create their assessments" on public.assessments;
create policy "owners create their assessments" on public.assessments
  for insert to authenticated with check ((select auth.uid()) = user_id);

drop policy if exists "owners delete their assessments" on public.assessments;
create policy "owners delete their assessments" on public.assessments
  for delete to authenticated using ((select auth.uid()) = user_id);
