# Deployment

| Part                                                | Where                                                | How it deploys                                                                                  |
| --------------------------------------------------- | ---------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| Web app                                             | Vercel, one project                                  | GitHub Actions builds and deploys it; Vercel's own Git deploys are off (`apps/web/vercel.json`) |
| API, Celery worker, scheduler, Redis, virus scanner | Render, from `render.yaml`                           | GitHub Actions asks Render to deploy the exact commit                                           |
| Database, sign-in, files                            | Supabase, one project per environment                | Migrations run in GitHub Actions before each deploy                                             |
| Errors                                              | Sentry: one project for the API, one for the web app | Reports carry no personal data (`app/privacy_logging.py`, `src/lib/error-reports.ts`)           |
| Product analytics                                   | PostHog (EU)                                         | Counts and labels only, no cookies, no resume content                                           |

## How a change reaches people

1. A push to `main` runs CI (`ci.yml`): lint, types, unit and database tests, Playwright e2e, the Docker
   image, and the backup drill.
2. When CI passes, `deploy.yml` deploys that commit to **staging**: migrations on the staging database,
   then the API, worker and scheduler on Render (waiting until each is live), then the web app as a Vercel
   preview at the staging address, then a check that `/health/ready` and the web app answer.
3. To release, open GitHub, Actions, **Deploy**, Run workflow, branch `main`, environment `production`.
   The same steps run against production with the latest commit on `main`. Only people with write
   access to the repository can start it.

Rolling back: run Deploy for production from an older commit (Actions, Deploy, pick the tag or branch),
or use Render's and Vercel's "rollback" buttons, which redeploy the previous build in seconds. Migrations
don't roll back by themselves; see [runbook.md](runbook.md#a-migration-broke-something).

## Monthly cost

Prices from Render's and Vercel's pricing pages; check them before you start. Supabase, Sentry and
PostHog have free plans that cover a small app.

| Item                                                                       | Staging | Production |
| -------------------------------------------------------------------------- | ------- | ---------- |
| Render: API, worker, scheduler (Starter, $7 each)                          | $21     | $21        |
| Render: Redis (Key Value Starter)                                          | $10     | $10        |
| Render: ClamAV private service (Standard, 2 GB; ClamAV needs about 1.5 GB) | $25     | $25        |
| Vercel Hobby (personal, non-commercial) or Pro ($20 a seat)                | shared  | shared     |
| OpenRouter (free model, or pay per use)                                    | $0+     | $0+        |

That is about $60 a month per environment on Render. To save money, delete the staging services on
Render when you aren't using them; the blueprint recreates them.

## Setting it up, once

Do these in order. Each secret is pasted into the service's own dashboard, never into the repo or chat.

### 1. Supabase: two projects

1. Keep the current project (`lycbtrlbgouloozdcwuy`) as **staging**.
2. Create the production project at https://supabase.com/dashboard/new/ (region close to your users).
3. In each project, note from Project Settings:
   - **Data API**: the project URL (`https://<ref>.supabase.co`).
   - **API Keys**: the publishable key and a secret key.
   - **Database, Connection string, Session pooler**: the URI, with the database password filled in.
4. In each project, Authentication, Sign In / Providers, JWT Keys: make sure the current key is
   **ECC (P-256)**. The API only accepts ES256 or RS256 tokens.
5. Authentication, URL Configuration: set Site URL to that environment's web address, and add
   `<web address>/auth/callback` and `careerfit://auth/callback` to Redirect URLs.
6. Database, Settings: turn on **Enforce SSL on incoming connections**.

### 2. Render: the blueprint

1. https://dashboard.render.com/blueprints, **New Blueprint Instance**, pick this repository and the
   `main` branch. Render reads `render.yaml` and creates the project with both environments.
2. It asks for each `sync: false` value per environment. Fill them in:

   | Key                                          | Value                                                                       |
   | -------------------------------------------- | --------------------------------------------------------------------------- |
   | `SUPABASE_URL`, `SUPABASE_SECRET_KEY`        | from that environment's Supabase project                                    |
   | `WEB_URL`                                    | the web address, e.g. `https://careerfit-staging.vercel.app`                |
   | `ALLOWED_ORIGINS`                            | the same address as a JSON list: `["https://careerfit-staging.vercel.app"]` |
   | `OPENROUTER_API_KEY`                         | from https://openrouter.ai/settings/keys (one key per environment)          |
   | `SENTRY_DSN`                                 | the API project's DSN (step 4)                                              |
   | `POSTHOG_PROJECT_TOKEN`                      | the PostHog project token (step 5)                                          |
   | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | test keys for staging (docs/payments.md)                                    |
   | `REVENUECAT_SECRET_KEY`, `EXPO_ACCESS_TOKEN` | as in local `.env`; may stay empty                                          |

3. Each API service's page shows its address (`https://careerfit-api-staging.onrender.com`) and each
   service's id (`srv-...`) in its URL. Note the ids of the API, worker and scheduler, per environment.
4. https://dashboard.render.com/u/settings#api-keys, **Create API Key**. Note it for GitHub.

### 3. Vercel: the web app

1. https://vercel.com/new, import this repository. Root Directory `apps/web`, framework Next.js.
2. Settings, Environment Variables. **Preview** holds staging's values, **Production** production's:
   `NEXT_PUBLIC_API_URL` (the Render API address), `NEXT_PUBLIC_SUPABASE_URL`,
   `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, `NEXT_PUBLIC_ENVIRONMENT` (`staging` or `production`),
   `NEXT_PUBLIC_SENTRY_DSN` (the web project's DSN), `NEXT_PUBLIC_POSTHOG_TOKEN`.
3. Settings, General: note the **Project ID**. Team settings: note the **Team ID** (the org id).
4. https://vercel.com/account/settings/tokens, create a token scoped to this project's team.

### 4. Sentry

1. https://sentry.io/signup/, then create two projects: platform **FastAPI** named `careerfit-api` and
   platform **Next.js** named `careerfit-web`. Copy each DSN.
2. In each project, Settings, Security & Privacy: turn on **Data Scrubber** and **Use Default
   Scrubbers**, and set **Prevent Storing of IP Addresses**.
3. Alerts, Create Alert, Issues: "a new issue is created", notify you by email. Do it for both projects.

### 5. PostHog

1. https://eu.posthog.com/signup (EU region). Copy the project token from Project settings.
2. Project settings: turn off **Autocapture** and **Session replay**, and turn on **Discard client IP
   data**. The app also turns them off in code.
3. Build the cost dashboard as in [runbook.md](runbook.md#dashboards).

### 6. GitHub: secrets and variables

Repository, Settings, Secrets and variables, Actions.

| Secret                                                  | Value                                                                                                   |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `RENDER_API_KEY`                                        | from step 2.4                                                                                           |
| `VERCEL_TOKEN`                                          | from step 3.4                                                                                           |
| `STAGING_SUPABASE_DB_URL`, `PRODUCTION_SUPABASE_DB_URL` | session pooler URIs from step 1.3                                                                       |
| `PRODUCTION_SUPABASE_SECRET_KEY`                        | production's secret key, for backups                                                                    |
| `BACKUP_PASSPHRASE`                                     | a long random passphrase; also keep it in your password manager, since backups can't be read without it |

| Variable                                                      | Value                                                                     |
| ------------------------------------------------------------- | ------------------------------------------------------------------------- |
| `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`                          | from step 3.3                                                             |
| `STAGING_RENDER_SERVICE_IDS`, `PRODUCTION_RENDER_SERVICE_IDS` | the three `srv-...` ids per environment, separated by spaces              |
| `STAGING_API_URL`, `PRODUCTION_API_URL`                       | the Render API addresses                                                  |
| `STAGING_WEB_DOMAIN`                                          | e.g. `careerfit-staging.vercel.app`; each staging deploy is pointed at it |
| `STAGING_WEB_URL`, `PRODUCTION_WEB_URL`                       | the web addresses, with `https://`, for uptime checks                     |
| `PRODUCTION_SUPABASE_URL`                                     | production's project URL, for backups                                     |

Then GitHub, your profile, Settings, Notifications, Actions: tick **Send notifications for failed
workflows only**, so uptime and backup failures email you.

### 7. First deploy

1. Actions, Deploy, Run workflow, `main`, `staging`. It applies all migrations to the staging database,
   so the staging project gets the same tables as now.
2. Open the staging web address, sign up, upload a resume, run an analysis.
3. Actions, Deploy, Run workflow, `main`, `production`.
4. Production's database starts with only the seed data. Load the job and skill data once with the
   scripts in `apps/api/scripts` (`seed_esco`, `seed_market`, `seed_translations`), pointed at
   production through `SUPABASE_URL` and `SUPABASE_SECRET_KEY` in the shell.
5. Point the phone app at production: set `EXPO_PUBLIC_API_URL`, `EXPO_PUBLIC_SUPABASE_URL`,
   `EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY` and `EXPO_PUBLIC_WEB_URL` in the EAS `production` environment.
