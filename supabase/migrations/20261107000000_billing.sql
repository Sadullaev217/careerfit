-- Paid plans. Stripe (web) and the app stores (phones) are the source of truth for payments; these tables
-- keep the API's copy of what each person is entitled to. Only the API writes them.

-- Where a Pro plan came from, and whether it ends at the close of the current period.
alter table public.subscriptions
  add column provider text check (provider in ('stripe', 'revenuecat')),
  add column cancel_at_period_end boolean not null default false;

-- Each Stripe event is handled once. Stripe can deliver the same event more than once.
create table public.stripe_events (
  id text primary key,
  type text not null,
  received_at timestamptz not null default now()
);
alter table public.stripe_events enable row level security;
revoke all on public.stripe_events from anon, authenticated;

-- One-time detailed report purchases, one per analysis. Deleting the analysis or the account removes them.
create table public.report_purchases (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  analysis_id uuid not null unique references public.analyses (id) on delete cascade,
  provider text not null check (provider in ('stripe', 'revenuecat')),
  provider_reference text not null unique,
  created_at timestamptz not null default now()
);
create index report_purchases_user_id_idx on public.report_purchases (user_id);
alter table public.report_purchases enable row level security;
revoke all on public.report_purchases from anon, authenticated;
grant select on public.report_purchases to authenticated;
create policy "own report purchases read" on public.report_purchases for select to authenticated
  using ((select auth.uid()) = user_id);

-- Starts an analysis only if the person is under their monthly limit. The lock makes two requests at the
-- same moment queue up, so both can't see "0 used" and go over. A null limit means unlimited (Pro).
-- Failed analyses don't count: those are our failures, not the person's use.
create function public.start_analysis_within_limit(
  p_user_id uuid,
  p_target_role_id uuid,
  p_document_id uuid,
  p_limit integer,
  p_period_start timestamptz
)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  used integer;
  new_id uuid;
begin
  perform pg_advisory_xact_lock(hashtextextended(p_user_id::text, 0));
  if p_limit is not null then
    select count(*) into used
    from public.analyses
    where user_id = p_user_id and created_at >= p_period_start and status <> 'failed';
    if used >= p_limit then
      return null;
    end if;
  end if;
  insert into public.analyses (user_id, target_role_id, document_id)
  values (p_user_id, p_target_role_id, p_document_id)
  returning id into new_id;
  return new_id;
end;
$$;
revoke execute on function public.start_analysis_within_limit(uuid, uuid, uuid, integer, timestamptz)
  from public, anon, authenticated;
