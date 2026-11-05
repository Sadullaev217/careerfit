-- Where to send "your report is ready". A token identifies one app install, never anything in a resume.
-- Deleting an account removes its tokens with it.
create table public.push_tokens (
  token text primary key,
  user_id uuid not null references auth.users (id) on delete cascade,
  platform text not null check (platform in ('ios', 'android')),
  language text not null default 'en' check (language in ('en', 'ru')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index push_tokens_user_id_idx on public.push_tokens (user_id);

-- Only the API writes and reads these, so a phone can't list or take over another person's alerts.
alter table public.push_tokens enable row level security;
revoke all on public.push_tokens from anon, authenticated;
