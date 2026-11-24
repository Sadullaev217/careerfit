# Deployment

CareerFit runs as a free public demo for a portfolio, in one environment named **staging**. Every part
is on a free plan; no payment card is attached to any of them.

| Part                     | Where                                                                    | How it deploys                                                                                  |
| ------------------------ | ------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------- |
| Web app                  | Vercel Hobby, project `careerfit-demo`                                   | GitHub Actions builds and deploys it; Vercel's own Git deploys are off (`apps/web/vercel.json`) |
| API and its AI jobs      | Modal Starter ($30 of free credits a month), app `careerfit-demo`        | GitHub Actions runs `modal deploy deploy/modal_app.py`                                          |
| AI model                 | OpenRouter, a free model (`OPENROUTER_MODEL`)                            | Nothing to deploy                                                                               |
| Database, sign-in, files | Supabase free, the existing project (`lycbtrlbgouloozdcwuy`)             | Migrations run in GitHub Actions before each deploy                                             |
| Errors, analytics        | Sentry and PostHog free plans (optional)                                 | Reports carry no personal data                                                                  |

Addresses: web `https://careerfit-demo.vercel.app`, API
`https://sadulloevshokhjakhon--careerfit-demo-api.us-east.modal.run`.

## How a change reaches the demo

1. A push to `main` runs CI (`ci.yml`): lint, types, unit and database tests, Playwright e2e, the Docker
   image, and the backup drill.
2. When CI passes, `deploy.yml` deploys that commit: migrations on the database; then the API on Modal,
   which builds the image from `apps/api/Dockerfile`; then the web app on Vercel; then a check that both
   answer.
3. To redeploy without a new commit: GitHub, Actions, **Deploy**, Run workflow, branch `main`.

Rolling back: run Deploy from an older commit. Vercel has Instant Rollback. Migrations don't roll back by
themselves; see [runbook.md](runbook.md#a-migration-broke-something).

## How the API runs on Modal

`deploy/modal_app.py` runs the API image as **one** container (`max_containers=1`):

- It starts on the first request (about 10 seconds) and stops after 5 minutes without any, so an idle
  demo spends no credits. The uptime check wakes it once an hour.
- There is no Redis or Celery worker. With `CELERY_TASK_ALWAYS_EAGER=true` each AI job runs in the same
  container right after the request that started it, and rate limits are counted in memory
  (`SINGLE_INSTANCE=true`), which is complete because there is one process.
- The jobs Celery beat runs on a full server are Modal cron functions: file and demo-account clean-up
  nightly at 03:30 UTC, the Job Bank refresh on Mondays at 06:00 UTC.
- ClamAV needs more memory than the demo has, so `MALWARE_SCANNER=off`, which the API allows only with
  `DEMO_MODE=true`. Uploads are still checked for type, size and structure, stay private, and are only
  parsed. The privacy policy says so.

Its settings are the Modal secret **careerfit-demo** (modal.com, Secrets):

| Key                                                    | Value                                                     |
| ------------------------------------------------------ | --------------------------------------------------------- |
| `ENVIRONMENT`                                          | `staging`                                                 |
| `SUPABASE_URL`, `SUPABASE_SECRET_KEY`                  | the project's address and secret key                      |
| `WEB_URL`                                              | `https://careerfit-demo.vercel.app`                       |
| `ALLOWED_ORIGINS`                                      | `["https://careerfit-demo.vercel.app"]`                   |
| `LLM_PROVIDER`, `OPENROUTER_API_KEY`                   | `openrouter` and the key                                  |
| `OLLAMA_FALLBACK`                                      | `false` (there is no local model)                         |
| `CELERY_TASK_ALWAYS_EAGER`, `SINGLE_INSTANCE`          | `true`, `true`                                            |
| `RATE_LIMIT_STORAGE`, `MALWARE_SCANNER`                | `memory://`, `off`                                        |
| `DEMO_MODE`, `DEMO_DAILY_AI_JOBS`, `DEMO_ACCOUNT_DAYS` | `true`, `15`, `30`                                        |
| `LLM_DAILY_BUDGET_USD`, `LLM_USER_DAILY_BUDGET_USD`    | `0`, `0` (the model is free; the budget check isn't run)  |
| `SENTRY_DSN`, `POSTHOG_PROJECT_TOKEN`                  | optional                                                  |

To change one: `modal secret create careerfit-demo --force KEY=value ...` with **all** keys, or edit it
in the dashboard, then redeploy.

## Demo mode

The API's `DEMO_MODE` turns on the public demo's settings (`app/demo.py`), and the web and phone apps show
it when `NEXT_PUBLIC_DEMO_MODE` and `EXPO_PUBLIC_DEMO_MODE` are `true`:

- Every account gets Pro and every detailed report; payments are off and the apps hide them.
- Documents and onboarding offer a made-up **sample resume**, so visitors needn't upload their own.
- At most `DEMO_DAILY_AI_JOBS` (15) resumes read plus analyses a day, for everyone together; then
  "come back tomorrow". OpenRouter's free models allow about 50 requests a day per account.
- Accounts and everything in them are deleted `DEMO_ACCOUNT_DAYS` (30) days after sign-up, by the
  nightly job. The banner and the privacy policy say so.

## Limits of the free setup

- **Modal**: $30 of credits a month. One awake container costs about $0.05 an hour, so the demo can be
  awake about 20 days a month in all; usage shows at modal.com, Usage. Without a card, running out stops
  the API until the next month instead of charging.
- **OpenRouter**: free models have a daily request limit and can be slow or removed. If the model goes,
  set `OPENROUTER_MODEL` in the secret to another `:free` model.
- **Vercel Hobby**: non-commercial use only, which a portfolio demo is.
- **Supabase free** pauses a project after a week without requests; the hourly uptime check keeps it
  awake.

## Setting it up, once

Already done for the current demo; these are the steps to rebuild it.

1. **Supabase.** Settings, API keys: the publishable key and a secret key. Database, Settings: reset the
   database password and turn on **Enforce SSL**. Authentication, URL Configuration: Site URL
   `https://careerfit-demo.vercel.app`; Redirect URLs `https://careerfit-demo.vercel.app/auth/callback`,
   `careerfit://auth/callback`.
2. **OpenRouter.** https://openrouter.ai/settings/keys: create a key.
3. **Modal.** Sign up at https://modal.com, then on your computer `uv tool install modal` and
   `modal token new`. Create the secret above, then `modal deploy deploy/modal_app.py`, which prints the
   API's address.
4. **Vercel.** New project `careerfit-demo`, Root Directory `apps/web`, Next.js. Environment Variables
   for Production and Preview: `NEXT_PUBLIC_API_URL` (the Modal address), `NEXT_PUBLIC_SUPABASE_URL`,
   `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, `NEXT_PUBLIC_ENVIRONMENT` = `staging`,
   `NEXT_PUBLIC_DEMO_MODE` = `true`, optionally `NEXT_PUBLIC_SENTRY_DSN` and
   `NEXT_PUBLIC_POSTHOG_TOKEN`. Account settings, Tokens: create a token for GitHub.
5. **GitHub.** Repository, Settings, Secrets and variables, Actions.

| Secret                        | Value                                                               |
| ----------------------------- | ------------------------------------------------------------------- |
| `MODAL_TOKEN_ID`              | from `~/.modal.toml`, or a new token at modal.com, Settings, Tokens |
| `MODAL_TOKEN_SECRET`          | the same token's secret                                             |
| `STAGING_SUPABASE_DB_URL`     | session pooler URI with the database password                       |
| `STAGING_SUPABASE_SECRET_KEY` | the Supabase secret key, for backups                                |
| `VERCEL_TOKEN`                | from step 4                                                         |
| `BACKUP_PASSPHRASE`           | a long random passphrase; keep it in your password manager too      |

| Variable                             | Value                                          |
| ------------------------------------ | ---------------------------------------------- |
| `STAGING_API_URL`                    | the Modal address                              |
| `STAGING_WEB_URL`                    | `https://careerfit-demo.vercel.app`            |
| `STAGING_SUPABASE_URL`               | `https://lycbtrlbgouloozdcwuy.supabase.co`     |
| `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` | the Vercel team ID and the project's ID        |

Deploys stay skipped until `STAGING_API_URL` is set. Then your GitHub profile, Settings, Notifications,
Actions: **Send notifications for failed workflows only**, so uptime and backup failures email you.

6. **Phone app.** Set `EXPO_PUBLIC_API_URL`, `EXPO_PUBLIC_SUPABASE_URL`,
   `EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, `EXPO_PUBLIC_WEB_URL` and `EXPO_PUBLIC_DEMO_MODE` = `true` in
   the EAS `preview` environment.

## Alternative: a server with its own AI model

`deploy/compose.yml`, `deploy/setup-server.sh` and `scripts/server-deploy.sh` run the whole stack (API,
Celery, Redis, ClamAV and an Ollama model, so resumes never reach an AI company) on one VM with at least
12 GB of memory, such as an Oracle Cloud Always Free Arm VM when one is available. That path needs the
server's `.env` from `deploy/server.env.example` and a deploy job over SSH in place of the Modal one;
see this file's history before 24 November 2026 for the full steps.
