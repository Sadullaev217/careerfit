-- Links each analysis to the resume it scored. Deleting the resume removes what was derived from it.
alter table public.analyses
  add column document_id uuid references public.documents (id) on delete cascade,
  add column error_code text;
create index analyses_document_id_idx on public.analyses (document_id);

-- Saved AI judgements, so the same resume and role always give the same score.
create table public.skill_judgements (
  document_id uuid not null references public.documents (id) on delete cascade,
  input_key text not null,
  result jsonb not null,
  created_at timestamptz not null default now(),
  primary key (document_id, input_key)
);

alter table public.skill_judgements enable row level security;
revoke all on public.skill_judgements from anon, authenticated;
