# Testing

| Level                                | Where                                                                                         | Runs in CI                             |
| ------------------------------------ | --------------------------------------------------------------------------------------------- | -------------------------------------- |
| Unit and integration (API)           | `apps/api/tests`, pytest. Database and row-security tests need Postgres (`TEST_DATABASE_URL`) | `api` job                              |
| Types and lint (web, mobile, shared) | `pnpm typecheck`, `pnpm lint`                                                                 | `js` job                               |
| End-to-end (web)                     | `apps/web/e2e`, Playwright                                                                    | `e2e` job, against a local Supabase    |
| End-to-end (mobile)                  | `apps/mobile/.maestro`, Maestro                                                               | By hand or on EAS (see below)          |
| Docker image                         | `apps/api/Dockerfile` builds and answers `/health`                                            | `docker` job                           |
| Real-model checks                    | `apps/api/eval` (bias audit, injection, scoring)                                              | No: they need a model and take minutes |

## Web end-to-end tests

The tests in `public-pages.spec.ts` need only the web app. `account-journey.spec.ts` signs in a throwaway
account, accepts the agreement, uploads a made-up resume (`e2e/fixtures/made-up-resume.pdf`), downloads the data export
and deletes the account. It creates the account through Supabase's admin API, so it needs:

- `E2E_SUPABASE_URL`: the Supabase project the web app and API use
- `E2E_SUPABASE_SECRET_KEY`: that project's secret key

Use a local or test project only, never production. Without them the journey test is skipped.

Run against your dev servers:

1. Start the API with the demo model, which answers instantly with a made-up profile:
   `LLM_PROVIDER=demo` (refused on staging and production). Celery must run eagerly
   (`CELERY_TASK_ALWAYS_EAGER=true`) or a worker must be running.
2. Start the web app: `pnpm --filter web dev`.
3. Once: `pnpm --filter web exec playwright install chromium`.
4. `pnpm --filter web e2e`, with the two variables above set in the shell.

## A local Supabase

CI starts one with `supabase start`, which needs Docker. The API only accepts ES256 or RS256 tokens,
so a signing key has to exist first. It is git-ignored; never commit it:

```
supabase gen signing-key --algorithm ES256 2>/dev/null | jq -s . > supabase/signing_keys.json
# then uncomment signing_keys_path in supabase/config.toml (don't commit that change)
supabase start
supabase status -o env
```

## Mobile end-to-end tests

The Maestro flows in `apps/mobile/.maestro` check the login screen, and that a signed-in account sees the
agreement before it can upload. The second flow needs a confirmed test account that hasn't agreed yet;
pass its details as `-e E2E_EMAIL=... -e E2E_PASSWORD=...` and never commit them.

- On your own emulator, with a development or preview build installed and
  [Maestro](https://docs.maestro.dev) set up: `maestro test apps/mobile/.maestro`
- On EAS, which builds the preview APK and runs the flows on its emulator:
  `npx eas-cli@latest workflow:run .eas/workflows/e2e-android.yml` from `apps/mobile`. Maestro jobs on
  EAS are in alpha and use the account's build minutes.
