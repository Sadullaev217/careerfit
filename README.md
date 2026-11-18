# CareerFit

Upload a resume and see how competitive you are for a role and region.

| Path              | What it is                            |
| ----------------- | ------------------------------------- |
| `apps/web`        | Next.js web app                       |
| `apps/mobile`     | Expo mobile app                       |
| `apps/api`        | FastAPI backend                       |
| `packages/shared` | Shared types, API client, Zod schemas |

## Prerequisites

Node 20+, pnpm, [uv](https://docs.astral.sh/uv/), and Docker (for local Postgres and Redis).

## Run locally

```bash
pnpm install
pnpm services
pnpm dev
```

- Web: http://localhost:3000
- API: http://localhost:8000/health
- Mobile: see below.

Copy each app's `.env.example` to `.env` to override defaults.

## Mobile app

The Expo app in `apps/mobile` has the web app's core flow, in English and Russian: sign in, add a resume
(a file, or pages scanned with the camera), choose a job and province, follow live progress, and read the
results. The last result is kept on the phone for offline viewing.

**Quick try in Expo Go** (no notifications, since Expo Go can't receive them):

```bash
adb reverse tcp:8000 tcp:8000   # the emulator reaches the API at localhost
adb reverse tcp:8081 tcp:8081
pnpm --filter mobile start:go
```

On a real phone, set `EXPO_PUBLIC_API_URL` in `apps/mobile/.env` to an address the phone can reach.

**Installed builds** use EAS, with the profiles in `apps/mobile/eas.json`: `development` (for testing
notifications), `preview` (an APK and an iPhone simulator app) and `production` (store builds). The
app belongs to the Expo project `@sadulllaev/careerfit` (`extra.eas.projectId` in `app.config.ts`).
Builds don't read `apps/mobile/.env`: its three `EXPO_PUBLIC_` values are set as EAS environment
variables instead (`eas env:list preview`). The cloud build compiles `packages/shared` itself, through
the `eas-build-post-install` script. Run EAS commands from `apps/mobile`:

```bash
npx eas-cli@latest build --profile preview --platform android
```

The store checklist, including privacy answers and account deletion, is in
[docs/mobile-release-checklist.md](docs/mobile-release-checklist.md).

**Report-ready notifications** need the Expo project above, and on Android the Firebase project
`careerfit-66b96`. Its `google-services.json` holds a Google API key, so it isn't in git: EAS builds get
it from the secret file variable `GOOGLE_SERVICES_JSON`, and local builds read `apps/mobile/google-services.json`
(download it from Firebase's project settings). The Firebase service account key is uploaded to Expo
under the project's Android credentials, and never stored in the repository. The API sends the messages
through Expo's push service; set `EXPO_ACCESS_TOKEN` only if push security is turned on at expo.dev.

## Supabase setup

1. Create a project at supabase.com. New projects use asymmetric JWT signing keys, which the API requires.
2. Apply the schema: `npx supabase link --project-ref <ref>`, then `npx supabase db push --remote`.
3. Fill in `SUPABASE_URL` and `SUPABASE_SECRET_KEY` in `apps/api/.env`, and the URL and publishable key in `apps/web/.env.local` and `apps/mobile/.env`. The secret key must stay server-side only.
4. Under Authentication > URL Configuration, allow `http://localhost:3000/auth/callback` and `careerfit://auth/callback`. The Google and Apple buttons only appear once those are enabled under Providers.
5. Connect your own mail service (custom SMTP) before real people sign up. Supabase's built-in email only reaches addresses on your organization's team, at most 2 messages an hour, with no delivery guarantee. Anyone else sees "We can't send email to this address yet".

Row-level security tests skip unless `TEST_DATABASE_URL` is set, and they wipe that database. CI always runs them; never point this variable at a real project.

## Background jobs and OCR

Uploaded files are parsed by a Celery worker, which needs Redis:

```bash
pnpm services
pnpm --filter api worker
```

Without Docker, set `CELERY_TASK_ALWAYS_EAGER=true` in `apps/api/.env` to parse inside the API process instead. Use this for local development only, because uploads then wait for parsing to finish.

Scanned PDFs need [Tesseract](https://tesseract-ocr.github.io/tessdoc/Installation.html) with the English and Russian language data on the PATH of whichever process does the parsing. Without it, scans fail with a clear message and other files still work.

## AI

By default, resumes are read by a model running on your own machine through [Ollama](https://ollama.com), so resume text doesn't leave it.

A hosted model through OpenRouter can be used instead, with Ollama as the fallback. Resume text then goes to OpenRouter and the model's provider. See [docs/ai-providers.md](docs/ai-providers.md).

```bash
ollama pull qwen3.5:4b
```

Skills are matched against ESCO, the EU's skills classification. Load it once per database:

```bash
cd apps/api
uv run --extra dev python -m scripts.seed_esco
```

Measure accuracy after changing the prompt, the model or the matching threshold. These need Ollama and the loaded skills:

```bash
uv run --extra dev python -m eval.run_eval
```

```bash
uv run --extra dev python -m eval.run_mapping_eval
```

All AI calls go through `apps/api/app/llm.py`, so moving to a hosted provider means adding one class there. A live deployment needs a GPU server or a hosted provider, and hosted providers must not reuse resume text for training.

## Job market data

Canada first, from [Job Bank open data](https://open.canada.ca/data/en/dataset/ea639e28-c0fc-48bf-b5dd-b8899bd43072) under the Open Government Licence – Canada, which allows commercial use and requires crediting the source. It has salary, occupation, location, and sometimes education and experience, but no job descriptions. So each occupation's skills come from ESCO instead, and describe what the occupation involves rather than what employers are asking for right now.

Load or refresh the data:

```bash
cd apps/api
uv run --extra dev python -m scripts.seed_market
```

A scheduled job refreshes postings weekly, which needs `pnpm --filter api worker` and `pnpm --filter api beat` running.

`apps/api/data/noc_esco_map.json` links Canadian occupations to ESCO ones. It was built by `scripts.build_occupation_map`, using similarity to shortlist and the local AI to decide, and should be reviewed before changing. New countries or sources are one more provider in `apps/api/app/job_sources.py`. Adzuna's API allows commercial use only during a 14-day trial, and its descriptions are shortened.

## Scoring

`apps/api/app/scoring.py` is plain arithmetic, so the same input gives the same score and every point has a written reason. Weights per field are in `apps/api/data/score_weights.json`, keyed by the first digit of the Canadian occupation code. Each set must total 100. A category with no market data is left out and its share goes to the others.

The only AI step decides what a resume shows for an occupation (`apps/api/app/skill_judgement.py`). It must cite evidence from the resume, code rejects claims without any, and similarity then gives partial credit for close skills it missed. A separate question decides which jobs and degrees are in this field, and code checks those too. Answers are saved per resume and question, so repeats reuse them. Bump `JUDGEMENT_VERSION` when changing the prompts or those rules.

The resume's name, contact details and protected details are removed before any AI sees it (`apps/api/app/resume_sanitizer.py`). The rules catch common layouts, not every wording, so model output is still untrusted. Check the effect of personal details with the real AI:

```bash
cd apps/api
uv run --extra dev python -m eval.run_fairness_eval
```

## Recommendations

`apps/api/app/recommendations.py` adds a report to each analysis, saved with its score in the `analyses` table. Gaps are ranked by how much closing each one would really add to the score, found by rescoring. Alternative roles are scored the same way as the target role, and the 30, 60 and 90 day plan is built from the actions.

AI only writes the suggested actions and resume rewrites. Code rejects links, statistics and invented details in actions, and limits where they send people to a fixed list. A rewrite must keep every number and name in the line and add almost nothing, because when the model was told which skills were missing, it wrote them into people's work history.

Job Bank ads don't list skills, so gaps can't be ranked by how often employers ask for them, and the report says so.

## Languages

The site is in English and Russian. Page text lives in `apps/web/src/i18n/en.json` and `ru.json`, and TypeScript refuses to build if a key is missing from either. Sentences the server writes, like score reasons, live in `apps/api/app/messages.py`, and a test checks both languages have the same messages. Reports stay in the language chosen when they were run.

ESCO has no Russian, so official skill and occupation names are translated by the local AI the first time they're needed and saved in `term_translations`. To translate occupation names ahead of time, so searching in Russian shows Russian names:

```bash
cd apps/api
uv run --extra dev python -m scripts.seed_translations --language ru
```

## Security and privacy

What is protected, how, and what is left is in [docs/security-checklist.md](docs/security-checklist.md).

- **Agreement first.** The API reads no resume until the person accepts the current privacy policy, terms and AI processing (`app/consent.py`). Changing what they agree to means changing `POLICY_DATE` there.
- **Limits and checks.** Requests are rate-limited (`app/rate_limit.py`), uploads are scanned by ClamAV when `MALWARE_SCANNER=clamav` (`docker compose --profile scan up -d clamav` locally), and logs and Sentry reports have personal data removed (`app/privacy_logging.py`).
- **Deployed servers.** With `ENVIRONMENT=staging` or `production` the API refuses to start without https addresses, Redis-backed limits, virus scanning and DEBUG off.
- **Retention.** Uploaded files are deleted 90 days after upload unless kept, by the daily `delete_expired_files` job in `pnpm --filter api beat`.
- **Export and deletion.** Settings has both. To check them against the real project with a throwaway account (it needs the AI model, and prints counts only):

```bash
cd apps/api
uv run --extra dev python -m scripts.check_data_rights
```

The bias audit and the prompt injection check run the real model on made-up resumes and fail if a score moves:

```bash
uv run --extra dev python -m eval.run_fairness_eval
```

```bash
uv run --extra dev python -m eval.run_injection_eval
```

## Checks

```bash
pnpm lint
pnpm typecheck
pnpm test
```

Pre-commit hooks: `uvx pre-commit install`.

End-to-end tests: `pnpm --filter web e2e` (web, Playwright) and the Maestro flows in
`apps/mobile/.maestro` (phone). See [docs/testing.md](docs/testing.md).

## Hosting

CareerFit runs as a free public demo, which gets every commit on `main` that passes CI. The API, workers and AI model run on one Oracle Cloud Always Free Arm server from [deploy/compose.yml](deploy/compose.yml) and `apps/api/Dockerfile`,
the web app on Vercel, the database and files on Supabase, errors go to Sentry and product analytics to
PostHog.

- [docs/deployment.md](docs/deployment.md): the pipeline, monthly cost and one-time setup
- [docs/runbook.md](docs/runbook.md): dashboards, alerts, incidents, backups and restoring
