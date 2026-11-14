# Runbook

What to do when something breaks. Start with "Where to look", then find the symptom below.

## Where to look

| Question                 | Place                                                                                                                                                |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| Is it up?                | GitHub, Actions, **Uptime** (every 10 minutes); `curl https://<api>/health/ready` names the part that's down: `database`, `queue` or `virus_scanner` |
| What error?              | Sentry, Issues, project `careerfit-api` or `careerfit-web`                                                                                           |
| What did the server log? | Render, the service, Logs. Logs carry no emails, tokens or resume text, only ids                                                                     |
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
day per budget. Change the budgets in the Render environment group, then redeploy.

## The site is down

1. `curl -i https://<api>/health` answers 200? If not, Render, the API service: is the latest deploy
   live? Logs show a crash on start? A start failing with "Unsafe settings for production" names the
   setting to fix in the environment group.
2. `/health/ready` says `database: unavailable`: check https://status.supabase.com and the project's
   page; a free project pauses after a week without traffic (Restore project).
3. `queue: unavailable`: Render, the Redis service. Uploads wait in the queue only while Redis is up.
4. `virus_scanner: unavailable`: Render, the ClamAV service. It needs about 1.5 GB of memory and a few
   minutes to load signatures after a restart. Uploads are refused (503) until it answers; nothing
   unscanned gets in.
5. The web app alone is down: Vercel, Deployments. Promote the previous deployment (Instant Rollback).

## A deploy failed

The Deploy run shows which job failed.

- **Database migrations**: nothing else was deployed, so the site still runs the old code. Fix the
  migration in a new commit. Never edit a migration that already ran anywhere.
- **API and workers**: the failed service keeps running its previous version. Render's deploy log says
  why (often a failing build or the settings check).
- **Web app**: the API is already new. Usually fine, because the API keeps old routes working.
- **Both answer after the deploy**: the new version isn't healthy. Roll back (below).

To roll back: Render, the service, Events, pick the last good deploy, **Rollback**; Vercel, Deployments,
**Instant Rollback**. Then fix forward.

## A migration broke something

Migrations only move forward. Write a new migration that undoes the change, push it, and let it deploy.
If data was lost, restore it from a backup into a new project (below) and copy back only what's needed.

## AI is slow, failing or expensive

- Reports fail with `ai_unavailable`: OpenRouter is down or the free model hit its daily limit. Check
  https://status.openrouter.ai and https://openrouter.ai/activity. Switch `OPENROUTER_MODEL` in the
  environment group to another model (docs/ai-providers.md lists the checked ones) and redeploy.
- A budget alert: open "Cost per account". One account far above the rest may be abuse: per-account
  limits already cap it at 20 analyses an hour. Delete the account in Supabase, Authentication, Users,
  if it breaks the terms.

## Someone asks for their data or its deletion

They can do both themselves in Settings (download a zip; delete the account). If they can't sign in,
confirm it's their email address, then delete the user in Supabase, Authentication, Users: their rows
cascade. Files in storage under `<user id>/` must be deleted too (Storage, documents bucket). Backups
age out within 14 days.

## A secret leaked

1. Rotate it where it was issued: Supabase (API Keys, create a new secret key, delete the old one),
   OpenRouter, Stripe, Render, Vercel, Sentry or PostHog.
2. Update it in Render's environment group or Vercel's environment variables, and in GitHub's secrets.
3. Redeploy. Check the service's logs for use you don't recognise.

## Backups and restoring

Every night `backup.yml` dumps production's database (roles, schema, data) and every uploaded file into
one archive, encrypted with `BACKUP_PASSPHRASE`, kept 14 days as an artifact of the Backup run. CI's
backup drill restores one on every push, so the procedure is known to work.

To restore:

1. Create a new Supabase project (never restore over the live one). Do step 1 of
   [deployment.md](deployment.md#1-supabase-two-projects) for it.
2. Actions, Backup, the run you want, download the artifact and unzip it to get the `.gpg` file.
3. With the Supabase CLI, `psql`, `uv` and `gpg` installed, from the repository root:
   ```
   export SUPABASE_DB_URL='<new project session pooler URI>'
   export SUPABASE_URL='https://<new ref>.supabase.co'
   export SUPABASE_SECRET_KEY='<new project secret key>'
   export BACKUP_PASSPHRASE='<from your password manager>'
   bash scripts/restore.sh careerfit-<time>.tar.gz.gpg
   ```
4. Point Render's environment group (`SUPABASE_URL`, `SUPABASE_SECRET_KEY`), Vercel's variables and
   the `PRODUCTION_*` GitHub secrets at the new project. Redeploy both.
5. Sign in with a test account and open an old result to check.
