#!/usr/bin/env bash
# Restores an archive from backup.sh into a Supabase project, following Supabase's restore guide.
# Restore into a NEW, empty project (or a fresh database), never over a live one: the schema step
# creates every table and fails if they exist. Then point the API and web app at it (docs/runbook.md).
#
# Needs: psql, uv, gpg, and in the environment
#   SUPABASE_DB_URL      the target project's Postgres connection string
#   SUPABASE_URL         the target project's https address, for the files
#   SUPABASE_SECRET_KEY  the target project's secret key
#   BACKUP_PASSPHRASE    the passphrase the backup was made with
# Usage: scripts/restore.sh <archive.tar.gz.gpg> [--database-only]
set -euo pipefail

: "${SUPABASE_DB_URL:?}" "${BACKUP_PASSPHRASE:?}"
archive="${1:?archive}"
root="$(cd "$(dirname "$0")/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

gpg --batch --decrypt --passphrase-fd 3 "$archive" 3<<< "$BACKUP_PASSPHRASE" | tar -C "$work" -xzf -
echo "Restoring the backup made at $(cat "$work/backup/created_at.txt")"

# Replica mode skips triggers while the data goes in, so rows aren't changed or duplicated on the way.
psql --single-transaction --variable ON_ERROR_STOP=1 \
  --file "$work/backup/roles.sql" \
  --file "$work/backup/schema.sql" \
  --command 'SET session_replication_role = replica' \
  --file "$work/backup/data.sql" \
  --dbname "$SUPABASE_DB_URL"

if [ "${2:-}" != --database-only ]; then
  : "${SUPABASE_URL:?}" "${SUPABASE_SECRET_KEY:?}"
  (cd "$root/apps/api" && uv run --python 3.12 python -m scripts.storage_backup restore "$work/backup/files")
fi
echo "Restore finished"
