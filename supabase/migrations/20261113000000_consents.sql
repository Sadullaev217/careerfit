-- What each person agreed to before their resume was processed, and when: the privacy policy, the terms
-- and AI processing, as one versioned agreement. A new version asks again. Withdrawing keeps the record
-- with the time it was withdrawn, so both can be shown later. Deleting the account removes it.
create table public.consents (
  user_id uuid not null references auth.users (id) on delete cascade,
  version text not null check (char_length(version) between 1 and 40),
  accepted_at timestamptz not null default now(),
  withdrawn_at timestamptz,
  primary key (user_id, version)
);
alter table public.consents enable row level security;
revoke all on public.consents from anon, authenticated;
grant select on public.consents to authenticated;
create policy "own consents read" on public.consents for select to authenticated
  using ((select auth.uid()) = user_id);
