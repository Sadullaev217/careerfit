-- MiniLM produces 384-dimension vectors. These columns are still empty, so nothing is lost.
alter table public.documents
  alter column embedding type extensions.vector(384) using null;
alter table public.skills
  alter column embedding type extensions.vector(384) using null;
alter table public.job_postings
  alter column embedding type extensions.vector(384) using null;

create index skills_embedding_idx on public.skills
  using hnsw (embedding extensions.vector_cosine_ops);

alter table public.documents add column extraction_status text
  check (extraction_status in ('pending', 'running', 'ready', 'failed'));
alter table public.documents add column extraction_error text;

create table public.extracted_profiles (
  document_id uuid primary key references public.documents (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  data jsonb not null,
  prompt_version text not null,
  model text not null,
  truncated boolean not null default false,
  suspicious_content boolean not null default false,
  created_at timestamptz not null default now()
);
create index extracted_profiles_user_id_idx on public.extracted_profiles (user_id);

alter table public.extracted_profiles enable row level security;
revoke all on public.extracted_profiles from anon, authenticated;
grant select on public.extracted_profiles to authenticated;
create policy "own extracted profiles read" on public.extracted_profiles for select to authenticated
  using ((select auth.uid()) = user_id);

-- A level isn't always stated, and "unknown" should not be recorded as a real level.
alter table public.profile_skills alter column level drop not null;
alter table public.profile_skills add column confidence numeric(3, 2) check (confidence between 0 and 1);
alter table public.profile_skills add column match_score numeric(3, 2);
alter table public.profile_skills add column source_name text;
-- Deleting the resume must also remove the skills that came from it.
alter table public.profile_skills add column source_document_id uuid
  references public.documents (id) on delete cascade;
create index profile_skills_source_document_id_idx on public.profile_skills (source_document_id);

create function public.match_skill(query_embedding extensions.vector(384))
returns table (id uuid, name text, esco_id text, similarity double precision)
language sql
stable
set search_path = ''
as $$
  select
    s.id,
    s.name,
    s.esco_id,
    1 - (s.embedding operator(extensions.<=>) query_embedding)
  from public.skills s
  where s.embedding is not null
  order by s.embedding operator(extensions.<=>) query_embedding
  limit 1;
$$;
revoke execute on function public.match_skill(extensions.vector) from public, anon, authenticated;
grant execute on function public.match_skill(extensions.vector) to service_role;
