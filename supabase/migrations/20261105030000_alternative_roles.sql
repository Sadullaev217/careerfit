-- The nearest distinct occupations to a text, for suggesting other roles a person could aim for.
create function public.match_occupations(
  query_embedding extensions.vector(384),
  match_count integer
)
returns table (occupation_code text, occupation_name text, similarity double precision)
language sql
stable
set search_path = ''
as $$
  select ranked.occupation_code, ranked.name, ranked.similarity
  from (
    select distinct on (nearest.occupation_code)
      nearest.occupation_code,
      o.name,
      nearest.similarity
    from (
      select
        t.occupation_code,
        1 - (t.embedding operator(extensions.<=>) query_embedding) as similarity
      from public.occupation_titles t
      where t.embedding is not null
      order by t.embedding operator(extensions.<=>) query_embedding
      limit 100
    ) nearest
    join public.occupations o on o.code = nearest.occupation_code
    order by nearest.occupation_code, nearest.similarity desc
  ) ranked
  order by ranked.similarity desc, ranked.occupation_code
  limit match_count;
$$;
revoke execute on function public.match_occupations(extensions.vector, integer) from public, anon, authenticated;
grant execute on function public.match_occupations(extensions.vector, integer) to service_role;
