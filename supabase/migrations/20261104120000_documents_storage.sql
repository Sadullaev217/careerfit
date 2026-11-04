alter table public.documents add column error_code text;

-- Clients must go through the API, which validates file contents before anything is stored.
revoke insert, delete on public.documents from authenticated;
drop policy "own documents insert" on public.documents;
drop policy "own documents delete" on public.documents;

-- No storage.objects policies are added: only the server's secret key can reach these files.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'documents',
  'documents',
  false,
  10485760,
  array[
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
  ]
)
on conflict (id) do nothing;
