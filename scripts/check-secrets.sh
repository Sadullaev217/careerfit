#!/usr/bin/env bash
# Fails if a committed file holds something shaped like a real key: Supabase secret keys, JWTs, Google API
# keys, Stripe secret and webhook keys, Anthropic and OpenRouter keys. Run from the repository root; CI runs
# it on every push. Prints only file names and line numbers, never the matching text.
set -euo pipefail

pattern='sb_secret_[A-Za-z0-9]|sk-ant-|eyJhbGci|AIza[0-9A-Za-z_-]{20,}|sk_test_[A-Za-z0-9]{10,}|sk_live_[A-Za-z0-9]{10,}|whsec_[A-Za-z0-9]{10,}|sk_[A-Za-z0-9]{20,}|sk-or-v1-[A-Za-z0-9]{10,}'

if matches=$(git grep -lIE "$pattern" -- . ':!pnpm-lock.yaml' ':!apps/api/uv.lock' ':!scripts/check-secrets.sh'); then
  echo "Possible secrets in these files (rotate any real key, then remove it):"
  git grep -nIE "$pattern" -- . ':!pnpm-lock.yaml' ':!apps/api/uv.lock' ':!scripts/check-secrets.sh' | cut -d: -f1,2
  exit 1
fi
echo "No secrets found."
