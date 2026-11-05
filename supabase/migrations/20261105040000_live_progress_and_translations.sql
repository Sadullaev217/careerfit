-- Which step a running analysis has reached, so the page can show live progress.
alter table public.analyses add column stage text;

-- ESCO has no Russian, and these names repeat across users, so each is translated once and kept.
-- They are official skill and occupation names, never anything from a resume.
create table public.term_translations (
  term text not null,
  language text not null,
  translation text not null,
  created_at timestamptz not null default now(),
  primary key (term, language)
);

alter table public.term_translations enable row level security;
revoke all on public.term_translations from anon, authenticated;
