# CareerFit

Upload a resume and see how competitive you are for a role and region.

| Path              | What it is                               |
| ----------------- | ---------------------------------------- |
| `apps/web`        | Next.js web app                          |
| `apps/mobile`     | Expo mobile app                          |
| `apps/api`        | FastAPI backend                          |
| `packages/shared` | Shared types, API client, Zod schemas    |

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
- Mobile: Expo dev server (press `a` or `i`). On an Android emulator or a real device, set `EXPO_PUBLIC_API_URL` to an address that reaches your machine.

Copy each app's `.env.example` to `.env` to override defaults.

## Supabase setup

1. Create a project at supabase.com. New projects use asymmetric JWT signing keys, which the API requires.
2. Apply the schema: `npx supabase link --project-ref <ref>`, then `npx supabase db push --remote`.
3. Fill in `SUPABASE_URL` and `SUPABASE_SECRET_KEY` in `apps/api/.env`, and the URL and publishable key in `apps/web/.env.local` and `apps/mobile/.env`. The secret key must stay server-side only.
4. Under Authentication > URL Configuration, allow `http://localhost:3000/auth/callback` and `careerfit://auth/callback`. Enable Google and Apple under Providers.

Row-level security tests skip unless `TEST_DATABASE_URL` is set, and they wipe that database. CI always runs them; never point this variable at a real project.

## Background jobs and OCR

Uploaded files are parsed by a Celery worker, which needs Redis:

```bash
pnpm services
pnpm --filter api worker
```

Without Docker, set `CELERY_TASK_ALWAYS_EAGER=true` in `apps/api/.env` to parse inside the API process instead. Use this for local development only, because uploads then wait for parsing to finish.

Scanned PDFs need [Tesseract](https://tesseract-ocr.github.io/tessdoc/Installation.html) with the English and Russian language data on the PATH of whichever process does the parsing. Without it, scans fail with a clear message and other files still work.

## AI (local)

Resumes are read by a model running on your own machine through [Ollama](https://ollama.com), so resume text doesn't leave it.

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

## Checks

```bash
pnpm lint
pnpm typecheck
pnpm test
```

Pre-commit hooks: `uvx pre-commit install`.
