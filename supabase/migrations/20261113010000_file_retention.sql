-- Uploaded files are deleted 90 days after upload unless the person chooses to keep them. The file and
-- its extracted text go; the skills and history read from it, and the results, stay until the person
-- deletes them. file_deleted_at says when that happened, so the apps can explain a missing file.
alter table public.documents
  add column keep boolean not null default false,
  add column file_deleted_at timestamptz;

-- The daily clean-up looks for old files nobody chose to keep.
create index documents_retention_idx on public.documents (created_at)
  where keep = false and file_deleted_at is null;
