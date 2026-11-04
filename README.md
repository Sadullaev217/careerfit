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

## Checks

```bash
pnpm lint
pnpm typecheck
pnpm test
```

Pre-commit hooks: `uvx pre-commit install`.
