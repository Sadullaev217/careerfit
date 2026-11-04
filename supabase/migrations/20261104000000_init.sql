create schema if not exists extensions;
create extension if not exists vector with schema extensions;

create type public.document_type as enum ('resume', 'cover_letter', 'portfolio_link');
create type public.document_status as enum ('pending', 'parsing', 'ready', 'failed');
create type public.analysis_status as enum ('pending', 'processing', 'completed', 'failed');
create type public.skill_level as enum ('beginner', 'intermediate', 'advanced', 'expert');
create type public.subscription_plan as enum ('free', 'pro');

create table public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  display_name text check (char_length(display_name) <= 200),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.documents (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  type public.document_type not null,
  file_name text,
  file_path text,
  url text,
  parsed_text text,
  status public.document_status not null default 'pending',
  embedding extensions.vector(1024),
  created_at timestamptz not null default now(),
  check ((type = 'portfolio_link') = (url is not null))
);
create index documents_user_id_idx on public.documents (user_id);

create table public.skills (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
  esco_id text unique,
  onet_id text,
  category text,
  embedding extensions.vector(1024)
);

create table public.profile_skills (
  user_id uuid not null references auth.users (id) on delete cascade,
  skill_id uuid not null references public.skills (id) on delete cascade,
  level public.skill_level not null,
  years numeric(4, 1) check (years >= 0),
  primary key (user_id, skill_id)
);
create index profile_skills_skill_id_idx on public.profile_skills (skill_id);

create table public.target_roles (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  title text not null check (char_length(title) between 1 and 200),
  region text not null check (char_length(region) between 1 and 100),
  industry text check (char_length(industry) <= 100),
  created_at timestamptz not null default now()
);
create index target_roles_user_id_idx on public.target_roles (user_id);

create table public.analyses (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  target_role_id uuid references public.target_roles (id) on delete set null,
  status public.analysis_status not null default 'pending',
  score numeric(5, 2) check (score between 0 and 100),
  result jsonb,
  created_at timestamptz not null default now(),
  completed_at timestamptz
);
create index analyses_user_id_created_at_idx on public.analyses (user_id, created_at desc);
create index analyses_target_role_id_idx on public.analyses (target_role_id);

create table public.job_postings (
  id uuid primary key default gen_random_uuid(),
  source text not null,
  source_id text not null,
  title text not null,
  region text not null,
  industry text,
  description text,
  salary_min numeric,
  salary_max numeric,
  salary_currency char(3),
  posted_at timestamptz,
  fetched_at timestamptz not null default now(),
  embedding extensions.vector(1024),
  unique (source, source_id)
);
create index job_postings_title_region_idx on public.job_postings (title, region);

create table public.job_skills (
  job_posting_id uuid not null references public.job_postings (id) on delete cascade,
  skill_id uuid not null references public.skills (id) on delete cascade,
  required boolean not null default true,
  primary key (job_posting_id, skill_id)
);
create index job_skills_skill_id_idx on public.job_skills (skill_id);

create table public.recommendations (
  id uuid primary key default gen_random_uuid(),
  analysis_id uuid not null references public.analyses (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  kind text not null,
  priority integer not null default 0,
  content jsonb not null,
  created_at timestamptz not null default now()
);
create index recommendations_analysis_id_idx on public.recommendations (analysis_id);
create index recommendations_user_id_idx on public.recommendations (user_id);

create table public.subscriptions (
  user_id uuid primary key references auth.users (id) on delete cascade,
  plan public.subscription_plan not null default 'free',
  status text not null default 'active',
  stripe_customer_id text unique,
  stripe_subscription_id text unique,
  current_period_end timestamptz,
  updated_at timestamptz not null default now()
);

create function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (id) values (new.id);
  insert into public.subscriptions (user_id) values (new.id);
  return new;
end;
$$;
revoke execute on function public.handle_new_user() from public, anon, authenticated;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

alter table public.profiles enable row level security;
alter table public.documents enable row level security;
alter table public.skills enable row level security;
alter table public.profile_skills enable row level security;
alter table public.target_roles enable row level security;
alter table public.analyses enable row level security;
alter table public.job_postings enable row level security;
alter table public.job_skills enable row level security;
alter table public.recommendations enable row level security;
alter table public.subscriptions enable row level security;

-- Supabase grants everything by default, so RLS alone would let users edit their own scores and plan.
revoke all on all tables in schema public from anon, authenticated;

grant select on public.profiles, public.documents, public.skills, public.profile_skills,
  public.target_roles, public.analyses, public.job_postings, public.job_skills,
  public.recommendations, public.subscriptions to authenticated;
grant update (display_name) on public.profiles to authenticated;
grant insert (type, file_name, file_path, url), delete on public.documents to authenticated;
grant insert (title, region, industry), update (title, region, industry), delete
  on public.target_roles to authenticated;

create policy "own profile read" on public.profiles for select to authenticated
  using ((select auth.uid()) = id);
create policy "own profile update" on public.profiles for update to authenticated
  using ((select auth.uid()) = id) with check ((select auth.uid()) = id);

create policy "own documents read" on public.documents for select to authenticated
  using ((select auth.uid()) = user_id);
create policy "own documents insert" on public.documents for insert to authenticated
  with check ((select auth.uid()) = user_id);
create policy "own documents delete" on public.documents for delete to authenticated
  using ((select auth.uid()) = user_id);

create policy "own target roles read" on public.target_roles for select to authenticated
  using ((select auth.uid()) = user_id);
create policy "own target roles insert" on public.target_roles for insert to authenticated
  with check ((select auth.uid()) = user_id);
create policy "own target roles update" on public.target_roles for update to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "own target roles delete" on public.target_roles for delete to authenticated
  using ((select auth.uid()) = user_id);

create policy "own profile skills read" on public.profile_skills for select to authenticated
  using ((select auth.uid()) = user_id);
create policy "own analyses read" on public.analyses for select to authenticated
  using ((select auth.uid()) = user_id);
create policy "own recommendations read" on public.recommendations for select to authenticated
  using ((select auth.uid()) = user_id);
create policy "own subscription read" on public.subscriptions for select to authenticated
  using ((select auth.uid()) = user_id);

create policy "skills readable" on public.skills for select to authenticated using (true);
create policy "job postings readable" on public.job_postings for select to authenticated using (true);
create policy "job skills readable" on public.job_skills for select to authenticated using (true);
