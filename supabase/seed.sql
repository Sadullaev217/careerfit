insert into public.skills (name, category) values
  ('Python', 'software'),
  ('SQL', 'software'),
  ('Project management', 'management'),
  ('Financial reporting', 'finance'),
  ('Patient care', 'healthcare')
on conflict (name) do nothing;

insert into public.job_postings (source, source_id, title, region, salary_min, salary_max, salary_currency)
values
  ('seed', 'backend-1', 'Backend Developer', 'US', 90000, 130000, 'USD'),
  ('seed', 'accountant-1', 'Accountant', 'US', 60000, 85000, 'USD')
on conflict (source, source_id) do nothing;

insert into public.job_skills (job_posting_id, skill_id, required)
select p.id, s.id, true
from public.job_postings p
join public.skills s on (p.source_id, s.name) in (
  ('backend-1', 'Python'),
  ('backend-1', 'SQL'),
  ('accountant-1', 'Financial reporting')
)
where p.source = 'seed'
on conflict do nothing;
