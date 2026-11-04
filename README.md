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
2. Apply the schema: `npx supabase link --project-ref <ref>`, then `npx supabase db push`.
3. Fill in `SUPABASE_URL` and `SUPABASE_SECRET_KEY` in `apps/api/.env`, and the URL and publishable key in `apps/web/.env.local` and `apps/mobile/.env`. The secret key must stay server-side only.
4. Under Authentication > URL Configuration, allow `http://localhost:3000/auth/callback` and `careerfit://auth/callback`. Enable Google and Apple under Providers.

Row-level security tests skip unless `TEST_DATABASE_URL` is set, and they wipe that database. CI always runs them; never point this variable at a real project.

## Checks

```bash
pnpm lint
pnpm typecheck
pnpm test
```

Pre-commit hooks: `uvx pre-commit install`.
