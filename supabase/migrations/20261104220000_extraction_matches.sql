-- profile_skills holds only the newest resume's skills, so each analysis keeps its own matches.
alter table public.extracted_profiles
  add column matched_skills jsonb not null default '[]'::jsonb;
