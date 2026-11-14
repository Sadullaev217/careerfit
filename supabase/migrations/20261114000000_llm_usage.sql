-- What each AI job cost, per person: tokens and dollars, never any text. One row per model per job
-- (reading a resume, scoring it, tailoring lines). Feeds the daily budget alerts and the cost dashboard.
create table public.llm_usage (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users (id) on delete cascade,
  job text not null check (char_length(job) between 1 and 40),
  model text not null check (char_length(model) between 1 and 200),
  calls integer not null check (calls > 0),
  prompt_tokens integer not null default 0 check (prompt_tokens >= 0),
  completion_tokens integer not null default 0 check (completion_tokens >= 0),
  cost_usd numeric(12, 6) not null default 0 check (cost_usd >= 0),
  created_at timestamptz not null default now()
);

create index llm_usage_created_at_idx on public.llm_usage (created_at);
create index llm_usage_user_id_idx on public.llm_usage (user_id, created_at);

-- Only the API writes and reads these. People get their own rows in the data export.
alter table public.llm_usage enable row level security;
revoke all on public.llm_usage from anon, authenticated;
