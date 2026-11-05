-- Reports how many ads share one pay figure. Without an employer column, a pay scale repeated by one
-- employer looks like a whole market agreeing, as with 354 Saskatchewan nursing ads at $75,213.
create or replace function public.market_stats(p_code text, p_region text default null)
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
    'salary_top_share', (
      select max(total)::float8 / nullif(sum(total), 0)
      from (select count(*) as total from unique_jobs
            where salary_mid is not null group by salary_mid) s
    ),
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
