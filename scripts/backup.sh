#!/usr/bin/env bash
# Backs up one Supabase project: database roles, schema and data, plus every uploaded file, into one
# encrypted archive. Follows Supabase's own backup guide (supabase db dump). Restore with restore.sh.
#
# Needs: supabase CLI, uv, gpg, and in the environment
#   SUPABASE_DB_URL      the project's Postgres connection string (session pooler, with password)
#   SUPABASE_URL         https://<ref>.supabase.co
#   SUPABASE_SECRET_KEY  the project's secret key, to read the files
#   BACKUP_PASSPHRASE    encrypts the archive; without it the backup can't be read, so keep it safe
# Usage: scripts/backup.sh <output folder>   ->  <folder>/careerfit-<UTC time>.tar.gz.gpg
set -euo pipefail

: "${SUPABASE_DB_URL:?}" "${SUPABASE_URL:?}" "${SUPABASE_SECRET_KEY:?}" "${BACKUP_PASSPHRASE:?}"
out="${1:?output folder}"
root="$(cd "$(dirname "$0")/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
mkdir -p "$out" "$work/backup/files"

# Storage's own bookkeeping and features CareerFit doesn't use belong to Supabase's storage role, which a
# restore can't write; a new project already has them. The files' rows (storage.objects) are kept.
internal=storage.migrations,storage.buckets_vectors,storage.vector_indexes,storage.buckets_analytics
supabase db dump --remote="$SUPABASE_DB_URL" -f "$work/backup/roles.sql" --role-only
supabase db dump --remote="$SUPABASE_DB_URL" -f "$work/backup/schema.sql"
supabase db dump --remote="$SUPABASE_DB_URL" -f "$work/backup/data.sql" --use-copy --data-only -x "$internal"
(cd "$root/apps/api" && uv run --python 3.12 python -m scripts.storage_backup backup "$work/backup/files")

date -u +%Y-%m-%dT%H:%M:%SZ > "$work/backup/created_at.txt"
archive="$out/careerfit-$(date -u +%Y%m%dT%H%M%SZ).tar.gz.gpg"
tar -C "$work" -czf - backup |
  gpg --batch --yes --symmetric --cipher-algo AES256 --passphrase-fd 3 -o "$archive" 3<<< "$BACKUP_PASSPHRASE"
echo "Backup written to $archive ($(du -h "$archive" | cut -f1))"
