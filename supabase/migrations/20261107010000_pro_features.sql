-- Pro: resume lines rewritten for one analysis's job. Saved so reopening the result doesn't ask the AI again.
-- Deleting the analysis, its resume or the account removes them.
create table public.tailored_rewrites (
  analysis_id uuid primary key references public.analyses (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  rewrites jsonb not null,
  model text not null,
  prompt_version text not null,
  created_at timestamptz not null default now()
);
create index tailored_rewrites_user_id_idx on public.tailored_rewrites (user_id);
alter table public.tailored_rewrites enable row level security;
revoke all on public.tailored_rewrites from anon, authenticated;
grant select on public.tailored_rewrites to authenticated;
create policy "own tailored rewrites read" on public.tailored_rewrites for select to authenticated
  using ((select auth.uid()) = user_id);
