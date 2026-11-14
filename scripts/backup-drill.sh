#!/usr/bin/env bash
# CI drill for backup.sh and restore.sh against a local Supabase (needs Docker and a running
# `supabase start`): makes an account with a document row and a file, backs up, rebuilds Supabase
# empty as a new project would be, restores, and checks all three came back.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
export BACKUP_PASSPHRASE="drill-only-not-a-real-passphrase"

load_status() {
  supabase status -o json > /tmp/sb.json
  export SUPABASE_URL=http://127.0.0.1:54321
  SUPABASE_SECRET_KEY="$(jq -r '.SECRET_KEY // .SERVICE_ROLE_KEY' /tmp/sb.json)"
  SUPABASE_DB_URL="$(jq -r '.DB_URL' /tmp/sb.json)"
  export SUPABASE_SECRET_KEY SUPABASE_DB_URL
}
api() { curl -sS --fail-with-body -H "apikey: $SUPABASE_SECRET_KEY" -H "Authorization: Bearer $SUPABASE_SECRET_KEY" "$@"; }

load_status
user=$(api -H "Content-Type: application/json" -d '{"email":"drill@example.com","password":"drill-only-password","email_confirm":true}' \
  "$SUPABASE_URL/auth/v1/admin/users" | jq -r .id)
api -H "Content-Type: application/pdf" --data-binary @apps/web/e2e/fixtures/made-up-resume.pdf \
  "$SUPABASE_URL/storage/v1/object/documents/$user/drill.pdf" > /dev/null
api -H "Content-Type: application/json" -H "Prefer: return=minimal" \
  -d "{\"user_id\":\"$user\",\"type\":\"resume\",\"file_name\":\"drill.pdf\",\"file_path\":\"$user/drill.pdf\"}" \
  "$SUPABASE_URL/rest/v1/documents"

bash scripts/backup.sh /tmp/drill
archive=$(ls /tmp/drill/*.gpg)

# A new project: Supabase's own schemas only, none of ours, no data.
supabase stop --no-backup
mv supabase/migrations /tmp/drill-migrations
mv supabase/seed.sql /tmp/drill-seed.sql
supabase start -x studio,imgproxy,edge-runtime,logflare,vector,supavisor,realtime,postgres-meta
mv /tmp/drill-migrations supabase/migrations
mv /tmp/drill-seed.sql supabase/seed.sql
load_status

bash scripts/restore.sh "$archive"

api "$SUPABASE_URL/auth/v1/admin/users/$user" | jq -e --arg id "$user" '.id == $id' > /dev/null
api "$SUPABASE_URL/rest/v1/documents?user_id=eq.$user&select=file_name" | jq -e 'length == 1' > /dev/null
api -o /tmp/restored.pdf "$SUPABASE_URL/storage/v1/object/documents/$user/drill.pdf"
cmp /tmp/restored.pdf apps/web/e2e/fixtures/made-up-resume.pdf
echo "Drill passed: the account, its document row and its file all came back"
