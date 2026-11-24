# Runbook

What to do when something breaks. Start with "Where to look", then find the symptom below.

## Where to look

| Question                 | Place                                                                                                                                                |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| Is it up?                | GitHub, Actions, **Uptime** (every 10 minutes); `curl https://<api>/health/ready` names the part that's down: `database`, `queue` or `virus_scanner` |
| What error?              | Sentry, Issues, project `careerfit-api` or `careerfit-web`                                                                                           |
| What did the server log? | On the VM: `cd ~/careerfit/current/deploy && docker compose logs --tail 100 api worker`. Logs carry no emails, tokens or resume text, only ids       |
| What changed?            | GitHub, Actions, **Deploy** runs; `git log`                                                                                                          |
| What is AI costing?      | PostHog, dashboard **AI cost**; or the SQL below in Supabase's SQL editor                                                                            |

## Dashboards

**Errors**: Sentry's Issues page per project, plus the email alert on new issues
([deployment.md](deployment.md#4-sentry)).

**AI cost**, in PostHog (https://eu.posthog.com), Dashboards, New dashboard, "AI cost", then add:

1. Insight, Trends, event `llm_usage`, measure **Property value sum** of `cost_usd`, interval Day.
   Title "AI cost per day ($)".
2. The same, broken down by `model`. Title "Cost by model".
3. The same, broken down by **distinct ID** (the account id), shown as a table, last 7 days.
   Title "Cost per account".
4. Event `llm_usage`, **Total count**, broken down by `job`. Title "AI jobs".

The same numbers from the database, in Supabase's SQL editor:

```sql
select date_trunc('day', created_at) as day, sum(cost_usd) as dollars, sum(calls) as calls,
       count(distinct user_id) as accounts
from llm_usage group by 1 order by 1 desc limit 30;
```

**Budget alerts**: the scheduler checks every hour. Past `LLM_DAILY_BUDGET_USD` for the day, or
`LLM_USER_DAILY_BUDGET_USD` for one account, it logs "Budget alert" and sends a Sentry warning, once a
day per budget. The demo uses a free model, so its budgets are 0, it doesn't run the check, and the counts are for interest.

## The site is down

1. `curl -i https://<api>/health` answers 200? The first request after a quiet spell wakes the API on
   Modal and takes about 10 seconds. If it fails, open modal.com, Apps, **careerfit-demo**: the
   container's logs show why. "Unsafe settings for staging" names the key to fix in the Modal secret
   `careerfit-demo` (docs/deployment.md); then run Deploy again. If Usage shows the month's free credits
   are spent, the API stays off until the next month.
2. `/health/ready` says `database: unavailable`: check https://status.supabase.com and the project's
   page; a free project pauses after a week without traffic (Restore project).
3. Analyses fail with an AI error: the free OpenRouter model may be at its daily limit or gone. Check
   https://openrouter.ai/activity; to switch, set `OPENROUTER_MODEL` in the secret to another `:free`
   model and redeploy.
4. `virus_scanner` is `off` on the demo by design (docs/deployment.md). On a server with ClamAV,
   `unavailable` means the `clamav` container: it needs about 1.5 GB of memory and a few minutes to load
   signatures, and uploads are refused (503) until it answers.
5. The web app alone is down: Vercel, Deployments. Promote the previous deployment (Instant Rollback).

## A deploy failed

The Deploy run shows which job failed.

- **Database migrations**: nothing else was deployed, so the site still runs the old code. Fix the
  migration in a new commit. Never edit a migration that already ran anywhere.
- **API, workers and AI on the server**: if the build failed, the old containers keep running. If the
  new ones started but never became ready, the run prints the last API and ClamAV logs.
- **Web app**: the API is already new. Usually fine, because the API keeps old routes working.
- **Both answer after the deploy**: the new version isn't healthy. Roll back (below).

To roll back: run Deploy from the last good commit, or on the VM
`cd ~/careerfit/releases/<good sha>/deploy && cp ~/careerfit/.env . && docker compose up -d --build`;
Vercel, Deployments, **Instant Rollback**. Then fix forward.

## A migration broke something

Migrations only move forward. Write a new migration that undoes the change, push it, and let it deploy.
If data was lost, restore it from a backup into a new project (below) and copy back only what's needed.

## AI is slow or failing

- Reports fail with `ai_unavailable`: the `ollama` container is down or the model isn't loaded.
  `docker compose ps ollama`, then `docker compose exec ollama ollama list`; if the model is missing,
  `docker compose exec ollama ollama pull qwen3.5:4b`.
- Reports fail with `timeout`: the two cores were too slow for the limit. Raise
  `AI_TASK_TIME_LIMIT_SECONDS` and `LLM_TIMEOUT_SECONDS` in `~/careerfit/.env`, then
  `docker compose up -d`.
- Everything waits: the worker runs one job at a time, so a queue builds when many people try at once.
  That is expected on the free server. One account far above the rest in "AI jobs" may be abuse:
  per-account limits already cap it at 20 analyses an hour. Delete the account in Supabase,
  Authentication, Users, if it breaks the terms.

## Someone asks for their data or its deletion

They can do both themselves in Settings (download a zip; delete the account). If they can't sign in,
confirm it's their email address, then delete the user in Supabase, Authentication, Users: their rows
cascade. Files in storage under `<user id>/` must be deleted too (Storage, documents bucket). Backups
age out within 14 days.

## A secret leaked

1. Rotate it where it was issued: Supabase (API Keys, create a new secret key, delete the old one),
   Stripe, Vercel, Sentry, PostHog, or the deploy SSH key (remove its line from the VM's
   `~/.ssh/authorized_keys` and make a new one).
2. Update it in the VM's `~/careerfit/.env`, Vercel's environment variables, and GitHub's secrets.
3. Redeploy. Check the service's logs for use you don't recognise.

## Backups and restoring

Every night `backup.yml` dumps staging's database (roles, schema, data) and every uploaded file into
one archive, encrypted with `BACKUP_PASSPHRASE`, kept 14 days as an artifact of the Backup run. CI's
backup drill restores one on every push, so the procedure is known to work.

To restore:

1. Create a new Supabase project (never restore over the live one). Do step 1 of
   [deployment.md](deployment.md#1-supabase) for it, with the new project's own keys.
2. Actions, Backup, the run you want, download the artifact and unzip it to get the `.gpg` file.
3. With the Supabase CLI, `psql`, `uv` and `gpg` installed, from the repository root:
   ```
   export SUPABASE_DB_URL='<new project session pooler URI>'
   export SUPABASE_URL='https://<new ref>.supabase.co'
   export SUPABASE_SECRET_KEY='<new project secret key>'
   export BACKUP_PASSPHRASE='<from your password manager>'
   bash scripts/restore.sh careerfit-<time>.tar.gz.gpg
   ```
4. Point the VM's `~/careerfit/.env` (`SUPABASE_URL`, `SUPABASE_SECRET_KEY`), Vercel's variables and
   the `STAGING_*` GitHub secrets and variables at the new project. Redeploy both.
5. Sign in with a test account and open an old result to check.
