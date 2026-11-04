-- salary_min and salary_max hold yearly amounts, already converted by the source reader.
alter table public.job_postings
  add column original_title text,
  add column occupation_code text,
  add column occupation_name text,
  add column economic_region text,
  add column city text,
  add column education_level text,
  add column experience_level text,
  add column employment_type text,
  add column vacancies integer not null default 1,
  add column duplicate_key text;

create index job_postings_occupation_region_idx on public.job_postings (occupation_code, region);
create index job_postings_posted_at_idx on public.job_postings (posted_at);

create table public.occupations (
  code text primary key,
  name text not null,
  esco_uri text,
  esco_title text,
  updated_at timestamptz not null default now()
);

create table public.occupation_titles (
  title text not null,
  occupation_code text not null references public.occupations (code) on delete cascade,
  posting_count integer not null default 0,
  embedding extensions.vector(384),
  primary key (title, occupation_code)
);
create index occupation_titles_code_idx on public.occupation_titles (occupation_code);
create index occupation_titles_embedding_idx on public.occupation_titles
  using hnsw (embedding extensions.vector_cosine_ops);

create table public.occupation_skills (
  occupation_code text not null references public.occupations (code) on delete cascade,
  skill_id uuid not null references public.skills (id) on delete cascade,
  required boolean not null,
  rank integer not null,
  primary key (occupation_code, skill_id)
);
create index occupation_skills_skill_id_idx on public.occupation_skills (skill_id);

alter table public.occupations enable row level security;
alter table public.occupation_titles enable row level security;
alter table public.occupation_skills enable row level security;
revoke all on public.occupations, public.occupation_titles, public.occupation_skills from anon, authenticated;
grant select on public.occupations, public.occupation_titles, public.occupation_skills to authenticated;
create policy "occupations readable" on public.occupations for select to authenticated using (true);
create policy "occupation titles readable" on public.occupation_titles for select to authenticated using (true);
create policy "occupation skills readable" on public.occupation_skills for select to authenticated using (true);

create function public.match_occupation(query_embedding extensions.vector(384))
returns table (title text, occupation_code text, occupation_name text, similarity double precision)
language sql
stable
set search_path = ''
as $$
  select
    t.title,
    t.occupation_code,
    o.name,
    1 - (t.embedding operator(extensions.<=>) query_embedding)
  from public.occupation_titles t
  join public.occupations o on o.code = t.occupation_code
  where t.embedding is not null
  order by t.embedding operator(extensions.<=>) query_embedding
  limit 1;
$$;
revoke execute on function public.match_occupation(extensions.vector) from public, anon, authenticated;
grant execute on function public.match_occupation(extensions.vector) to service_role;

-- Each ad counts once here, because one spam ad repeated 938 times made retail pay look like $111,360.
create function public.market_stats(p_code text, p_region text default null)
returns jsonb
language sql
stable
set search_path = ''
as $$
  with unique_jobs as (
    select distinct on (duplicate_key)
      (salary_min + salary_max) / 2 as salary_mid,
      posted_at,
      education_level,
      experience_level
    from public.job_postings
    where occupation_code = p_code
      and (p_region is null or region = p_region)
    order by duplicate_key, posted_at desc
  )
  select jsonb_build_object(
    'sample_size', count(*),
    'salary_sample_size', count(salary_mid),
    'salary_p25', percentile_cont(0.25) within group (order by salary_mid::float8),
    'salary_median', percentile_cont(0.5) within group (order by salary_mid::float8),
    'salary_p75', percentile_cont(0.75) within group (order by salary_mid::float8),
    'latest_posting', max(posted_at)::date,
    'education', (
      select coalesce(jsonb_object_agg(level, total), '{}'::jsonb)
      from (select education_level as level, count(*) as total from unique_jobs
            where education_level is not null group by 1) e
    ),
    'experience', (
      select coalesce(jsonb_object_agg(level, total), '{}'::jsonb)
      from (select experience_level as level, count(*) as total from unique_jobs
            where experience_level is not null group by 1) x
    )
  )
  from unique_jobs;
$$;
revoke execute on function public.market_stats(text, text) from public, anon, authenticated;
grant execute on function public.market_stats(text, text) to service_role;
