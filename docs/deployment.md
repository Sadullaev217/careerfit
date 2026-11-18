# Deployment

CareerFit is hosted in one environment, **staging**, as a portfolio demo. There is no production
environment; the last section says what adding one would take.

| Part                                                | Where                                                   | How it deploys                                                                                  |
| --------------------------------------------------- | ------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| Web app                                             | Vercel                                                  | GitHub Actions builds and deploys it; Vercel's own Git deploys are off (`apps/web/vercel.json`) |
| API, Celery worker, scheduler, Redis, virus scanner | Render, from `render.yaml`                              | GitHub Actions asks Render to deploy the exact commit                                           |
| Database, sign-in, files                            | Supabase, the existing project (`lycbtrlbgouloozdcwuy`) | Migrations run in GitHub Actions before each deploy                                             |
| Errors                                              | Sentry: one project for the API, one for the web app    | Reports carry no personal data (`app/privacy_logging.py`, `src/lib/error-reports.ts`)           |
| Product analytics                                   | PostHog (EU)                                            | Counts and labels only, no cookies, no resume content                                           |

## How a change reaches staging

1. A push to `main` runs CI (`ci.yml`): lint, types, unit and database tests, Playwright e2e, the Docker
   image, and the backup drill.
2. When CI passes, `deploy.yml` deploys that commit to staging: migrations on the database, then the API,
   worker and scheduler on Render (waiting until each is live), then the web app on Vercel at the staging
   address, then a check that `/health/ready` and the web app answer.
3. To redeploy without a new commit: GitHub, Actions, **Deploy**, Run workflow, branch `main`.

Rolling back: Render's and Vercel's rollback buttons redeploy the previous build in seconds. Migrations
don't roll back by themselves; see [runbook.md](runbook.md#a-migration-broke-something).

## Monthly cost

Prices from Render's and Vercel's pricing pages; check them before you start. Supabase, Sentry, PostHog
and Vercel Hobby (personal, non-commercial use) have free plans that cover a demo.

| Item                                                                       | Per month     |
| -------------------------------------------------------------------------- | ------------- |
| Render: API, worker, scheduler (Starter, $7 each)                          | $21           |
| Render: Redis (Key Value Starter)                                          | $10           |
| Render: ClamAV private service (Standard, 2 GB; ClamAV needs about 1.5 GB) | $25           |
| OpenRouter (free model, or pay per use)                                    | $0+           |
| **Total**                                                                  | **about $56** |

Render bills by the second while services exist. To pause the cost, delete the services in Render when
you aren't showing the demo; New Blueprint Instance recreates them from `render.yaml`.

## Setting it up, once

Do these in order. Each secret is pasted into the service's own dashboard, never into the repo or chat.

### 1. Supabase

The existing project becomes staging; it already has the tables and the job and skill data.

1. Open https://supabase.com/dashboard/project/lycbtrlbgouloozdcwuy/settings/api-keys and note the
   **publishable key** and a **secret key**. If the secret key was ever pasted anywhere, create a new
   one here and delete the old one first.
2. **Connect** (top of the project page), **Session pooler**: copy the URI and put the database password
   into it. That is `STAGING_SUPABASE_DB_URL` for GitHub.
3. Authentication, Sign In / Providers, **JWT Keys**: the current key must be **ECC (P-256)**. The API
   only accepts ES256 or RS256 tokens.
4. Authentication, **URL Configuration**: Site URL = the staging web address (step 3), and add
   `<web address>/auth/callback` and `careerfit://auth/callback` to Redirect URLs.
5. Database, Settings: turn on **Enforce SSL on incoming connections**.

### 2. Render

1. https://dashboard.render.com/blueprints, **New Blueprint Instance**, pick this repository and the
   `main` branch. Render reads `render.yaml` and creates the staging environment.
2. It asks for each `sync: false` value. Fill them in:

   | Key                                          | Value                                                                       |
   | -------------------------------------------- | --------------------------------------------------------------------------- |
   | `SUPABASE_URL`                               | `https://lycbtrlbgouloozdcwuy.supabase.co`                                  |
   | `SUPABASE_SECRET_KEY`                        | from step 1.1                                                               |
   | `WEB_URL`                                    | the staging web address, e.g. `https://careerfit-staging.vercel.app`        |
   | `ALLOWED_ORIGINS`                            | the same address as a JSON list: `["https://careerfit-staging.vercel.app"]` |
   | `OPENROUTER_API_KEY`                         | from https://openrouter.ai/settings/keys                                    |
   | `SENTRY_DSN`                                 | the API project's DSN (step 4)                                              |
   | `POSTHOG_PROJECT_TOKEN`                      | the PostHog project token (step 5)                                          |
   | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | Stripe **test** keys (docs/payments.md)                                     |
   | `REVENUECAT_SECRET_KEY`, `EXPO_ACCESS_TOKEN` | as in local `.env`; may stay empty                                          |

3. The API service's page shows its address (`https://careerfit-api-staging.onrender.com`). Each
   service's id (`srv-...`) is in its page URL. Note the ids of the API, worker and scheduler.
4. https://dashboard.render.com/u/settings#api-keys, **Create API Key**. Note it for GitHub.

### 3. Vercel

1. https://vercel.com/new, import this repository. Root Directory `apps/web`, framework Next.js.
2. Settings, Environment Variables, environment **Preview** (staging deploys are previews):
   `NEXT_PUBLIC_API_URL` (the Render API address), `NEXT_PUBLIC_SUPABASE_URL`,
   `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, `NEXT_PUBLIC_ENVIRONMENT` = `staging`,
   `NEXT_PUBLIC_SENTRY_DSN` (the web project's DSN), `NEXT_PUBLIC_POSTHOG_TOKEN`.
3. Settings, General: note the **Project ID**. Team or account settings: note the **Team ID**.
4. https://vercel.com/account/settings/tokens, create a token. Note it for GitHub.
5. Pick the staging address, e.g. `careerfit-staging.vercel.app`; each deploy is pointed at it.

### 4. Sentry

1. https://sentry.io/signup/, then create two projects: platform **FastAPI** named `careerfit-api` and
   platform **Next.js** named `careerfit-web`. Copy each DSN.
2. In each project, Settings, Security & Privacy: turn on **Data Scrubber** and **Use Default
   Scrubbers**, and **Prevent Storing of IP Addresses**.
3. Alerts, Create Alert, Issues: "a new issue is created", notify you by email. For both projects.

### 5. PostHog

1. https://eu.posthog.com/signup (EU region). Copy the project token from Project settings.
2. Project settings: turn off **Autocapture** and **Session replay**, and turn on **Discard client IP
   data**. The app also turns them off in code.
3. Build the cost dashboard as in [runbook.md](runbook.md#dashboards).

### 6. GitHub

Repository, Settings, Secrets and variables, Actions.

| Secret                        | Value                                                                                                  |
| ----------------------------- | ------------------------------------------------------------------------------------------------------ |
| `RENDER_API_KEY`              | from step 2.4                                                                                          |
| `VERCEL_TOKEN`                | from step 3.4                                                                                          |
| `STAGING_SUPABASE_DB_URL`     | from step 1.2                                                                                          |
| `STAGING_SUPABASE_SECRET_KEY` | from step 1.1, for backups                                                                             |
| `BACKUP_PASSPHRASE`           | a long random passphrase; keep it in your password manager too, since backups can't be read without it |

| Variable                             | Value                                                      |
| ------------------------------------ | ---------------------------------------------------------- |
| `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` | from step 3.3                                              |
| `STAGING_RENDER_SERVICE_IDS`         | the three `srv-...` ids from step 2.3, separated by spaces |
| `STAGING_API_URL`                    | the Render API address                                     |
| `STAGING_WEB_DOMAIN`                 | from step 3.5, without `https://`                          |
| `STAGING_WEB_URL`                    | the same with `https://`, for uptime checks                |
| `STAGING_SUPABASE_URL`               | `https://lycbtrlbgouloozdcwuy.supabase.co`, for backups    |

Then GitHub, your profile, Settings, Notifications, Actions: tick **Send notifications for failed
workflows only**, so uptime and backup failures email you.

### 7. First deploy

1. The pipeline runs from `main`, so the Part 10, 11 and 12 branches must be merged first.
2. Actions, Deploy, Run workflow, `main`.
3. Open the staging web address, sign up, upload a resume, run an analysis. Check that Sentry and
   PostHog received something (PostHog: Activity; Sentry stays empty until an error happens).
4. To use the phone app with staging, set `EXPO_PUBLIC_API_URL`, `EXPO_PUBLIC_SUPABASE_URL`,
   `EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY` and `EXPO_PUBLIC_WEB_URL` in the EAS `preview` environment.

## Adding production later

1. A second Supabase project, with the job and skill data loaded by the scripts in `apps/api/scripts`.
2. A copy of the staging block in `render.yaml` named `production`, with its own service names.
3. Back in `deploy.yml`, a manual job calling `deploy-environment.yml` with `environment: production`;
   that workflow already reads `PRODUCTION_*` secrets and variables.
4. Vercel's **Production** environment variables, and `PRODUCTION_*` entries in GitHub.
