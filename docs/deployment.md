# Deployment

CareerFit runs as a free public demo for a portfolio, in one environment named **staging**. Every part
is on a free plan, and the AI model runs on the demo's own server, so resumes don't go to an AI company.

| Part                                                 | Where                                                                     | How it deploys                                                                                  |
| ---------------------------------------------------- | ------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| Web app                                              | Vercel Hobby (free, non-commercial)                                       | GitHub Actions builds and deploys it; Vercel's own Git deploys are off (`apps/web/vercel.json`) |
| API, Celery worker, scheduler, Redis, ClamAV, Ollama | One Oracle Cloud Always Free Arm VM, from `deploy/compose.yml`            | GitHub Actions copies the commit over SSH and runs `scripts/server-deploy.sh`                   |
| HTTPS for the API                                    | Caddy on the VM, with a free Let's Encrypt certificate for a DuckDNS name | Automatic                                                                                       |
| Database, sign-in, files                             | Supabase free, the existing project (`lycbtrlbgouloozdcwuy`)              | Migrations run in GitHub Actions before each deploy                                             |
| Errors, analytics                                    | Sentry and PostHog free plans                                             | Reports carry no personal data                                                                  |

## How a change reaches the demo

1. A push to `main` runs CI (`ci.yml`): lint, types, unit and database tests, Playwright e2e, the Docker
   image for both Intel and Arm, the server's compose file, and the backup drill.
2. When CI passes, `deploy.yml` deploys that commit: migrations on the database; then the commit is
   copied to the VM, where the images are built and started, the AI model is pulled if missing, and the
   script waits until `/health/ready` passes; then the web app on Vercel; then a check that both answer.
3. To redeploy without a new commit: GitHub, Actions, **Deploy**, Run workflow, branch `main`.

Rolling back: run Deploy from an older commit, or on the VM `cd ~/careerfit/current/deploy` of an older
release and `docker compose up -d`. Vercel has Instant Rollback. Migrations don't roll back by
themselves; see [runbook.md](runbook.md#a-migration-broke-something).

## Limits of the free setup

- **The VM**: Oracle's Always Free Arm allowance is 2 cores and 12 GB of memory
  ([Oracle's page](https://docs.oracle.com/en-us/iaas/Content/FreeTier/resourceref.htm)). The model,
  ClamAV and the app fit, with 4 GB of swap for spikes.
- **Speed**: the model runs on those 2 cores without a GPU, so a full analysis takes several minutes,
  and the worker runs one job at a time; others wait in the queue. The limits in `.env` allow for this
  (`LLM_TIMEOUT_SECONDS=900`, `AI_TASK_TIME_LIMIT_SECONDS=2400`).
- **Idle reclaim**: Oracle may reclaim an Always Free VM that is idle for 7 days (CPU, network and
  memory all under 20%). Ollama keeps the model loaded (`OLLAMA_KEEP_ALIVE=-1`), which holds memory use
  above that line. Upgrading the account to Pay As You Go removes the risk and still costs nothing
  within the free allowance.
- **Supabase free** pauses a project after a week without requests; the uptime check every 10 minutes
  keeps it awake.

## Setting it up, once

Do these in order. Each secret goes into the service's own dashboard or the server's `.env`, never into
the repository or a chat.

### 1. Oracle Cloud: the VM

1. Sign up at https://signup.cloud.oracle.com (a card is asked for to verify identity; Always Free
   resources aren't charged). Pick a home region with Arm capacity; it can't be changed later.
2. Menu, Compute, Instances, **Create instance**:
   - Image: **Canonical Ubuntu 24.04** (the aarch64 one).
   - Shape: **Ampere**, `VM.Standard.A1.Flex`, **2 OCPUs**, **12 GB** memory.
   - Networking: create a new VCN and public subnet, **Assign a public IPv4 address**.
   - SSH keys: **Generate a key pair for me**, and download the private key. This is your own login.
   - Boot volume: 100 GB.
     If it says "Out of capacity", try another availability domain or try again later.
3. The instance's page, Subnet, Default Security List, **Add Ingress Rules**: source `0.0.0.0/0`,
   TCP, destination port `80`; and another for port `443`.
4. Note the instance's **public IP**.
5. Log in: `ssh -i <your key> ubuntu@<public IP>`, then copy `deploy/setup-server.sh` over and run
   `bash setup-server.sh`. Log out and back in.
6. For GitHub's deploys, make a separate key on your own computer:
   `ssh-keygen -t ed25519 -f careerfit-deploy -N ""`, then append `careerfit-deploy.pub` to the
   server's `~/.ssh/authorized_keys`.
7. On your computer: `ssh-keyscan <public IP>` prints the server's host key lines. Keep them for GitHub.

### 2. DuckDNS: the API's address

1. https://www.duckdns.org, sign in, add a subdomain, e.g. `careerfit-api`, and set its IP to the
   VM's public IP. The API will be at `https://careerfit-api.duckdns.org`.

### 3. Supabase

The existing project serves the demo; it already has the tables and the job and skill data.

1. https://supabase.com/dashboard/project/lycbtrlbgouloozdcwuy/settings/api-keys: note the
   **publishable key** and a **secret key**. If the secret key was ever pasted anywhere, create a new
   one and delete the old one first.
2. **Connect** (top of the project page), **Session pooler**: copy the URI and put the database password
   into it. That is `STAGING_SUPABASE_DB_URL` for GitHub.
3. Authentication, Sign In / Providers, **JWT Keys**: the current key must be **ECC (P-256)**.
4. Authentication, **URL Configuration**: Site URL = the web address (step 4), and add
   `<web address>/auth/callback` and `careerfit://auth/callback` to Redirect URLs.
5. Database, Settings: turn on **Enforce SSL on incoming connections**.

### 4. Vercel: the web app

1. https://vercel.com/new, import this repository. Project name e.g. `careerfit-demo`, Root Directory
   `apps/web`, framework Next.js. The address is then `https://careerfit-demo.vercel.app`.
2. Settings, Environment Variables, environment **Production**:
   `NEXT_PUBLIC_API_URL` = `https://careerfit-api.duckdns.org`, `NEXT_PUBLIC_SUPABASE_URL`,
   `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, `NEXT_PUBLIC_ENVIRONMENT` = `staging`, and optionally
   `NEXT_PUBLIC_SENTRY_DSN` and `NEXT_PUBLIC_POSTHOG_TOKEN`.
3. Settings, General: note the **Project ID**. Account settings: note your **Team ID**.
4. https://vercel.com/account/settings/tokens: create a token. Note it for GitHub.

### 5. The server's settings

1. On the VM: `nano ~/careerfit/.env`, paste the contents of `deploy/server.env.example`, and fill in
   `API_DOMAIN` (step 2, without `https://`), `SUPABASE_SECRET_KEY` (step 3.1), and `WEB_URL` and
   `ALLOWED_ORIGINS` (step 4.1). Save with Ctrl+O, Enter, Ctrl+X.
2. `chmod 600 ~/careerfit/.env`, so only your user can read it.

### 6. Sentry and PostHog (optional)

1. https://sentry.io/signup/: projects `careerfit-api` (FastAPI) and `careerfit-web` (Next.js). In
   each, Settings, Security & Privacy: **Data Scrubber**, **Use Default Scrubbers**, **Prevent Storing
   of IP Addresses**. Alerts: email on new issues. Put the DSNs in `.env` and Vercel.
2. https://eu.posthog.com/signup: turn off Autocapture and Session replay, turn on Discard client IP
   data. Put the project token in `.env` and Vercel. Dashboard: [runbook.md](runbook.md#dashboards).

### 7. GitHub

Repository, Settings, Secrets and variables, Actions.

| Secret                        | Value                                                             |
| ----------------------------- | ----------------------------------------------------------------- |
| `STAGING_SSH_KEY`             | the private key `careerfit-deploy` from step 1.6 (the whole file) |
| `STAGING_SSH_KNOWN_HOSTS`     | the lines from step 1.7                                           |
| `STAGING_SUPABASE_DB_URL`     | from step 3.2                                                     |
| `STAGING_SUPABASE_SECRET_KEY` | from step 3.1, for backups                                        |
| `VERCEL_TOKEN`                | from step 4.4                                                     |
| `BACKUP_PASSPHRASE`           | a long random passphrase; keep it in your password manager too    |

| Variable                             | Value                                      |
| ------------------------------------ | ------------------------------------------ |
| `STAGING_SSH_HOST`                   | the VM's public IP                         |
| `STAGING_API_URL`                    | `https://careerfit-api.duckdns.org`        |
| `STAGING_WEB_URL`                    | `https://careerfit-demo.vercel.app`        |
| `STAGING_SUPABASE_URL`               | `https://lycbtrlbgouloozdcwuy.supabase.co` |
| `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` | from step 4.3                              |

Then your GitHub profile, Settings, Notifications, Actions: **Send notifications for failed workflows
only**, so uptime and backup failures email you.

### 8. First deploy

1. The pipeline runs from `main`, so the Part 10, 11 and 12 branches must be merged first.
2. Actions, Deploy, Run workflow, `main`. The first run takes longest: it builds the image on the VM
   and downloads the model (about 3 GB) and ClamAV's signatures.
3. Open the web address, sign up, upload a resume, run an analysis.
4. For the phone app, set `EXPO_PUBLIC_API_URL`, `EXPO_PUBLIC_SUPABASE_URL`,
   `EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY` and `EXPO_PUBLIC_WEB_URL` in the EAS `preview` environment.
