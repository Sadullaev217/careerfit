'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { createApiClient, type HealthResponse } from '@careerfit/shared';

const api = createApiClient(process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000');

type State =
  | { kind: 'loading' }
  | { kind: 'ok'; health: HealthResponse }
  | { kind: 'error'; message: string };

export default function Home() {
  const [state, setState] = useState<State>({ kind: 'loading' });

  useEffect(() => {
    api.health
      .check()
      .then((health) => setState({ kind: 'ok', health }))
      .catch((err: unknown) =>
        setState({ kind: 'error', message: err instanceof Error ? err.message : 'Unknown error' }),
      );
  }, []);

  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col justify-center gap-4 p-8">
      <h1 className="text-3xl font-semibold">CareerFit</h1>
      <p role="status" data-testid="api-status">
        {state.kind === 'loading' && 'Checking API…'}
        {state.kind === 'ok' && `API status: ${state.health.status} (v${state.health.version})`}
        {state.kind === 'error' && `API unreachable: ${state.message}`}
      </p>
      <Link className="underline" href="/account">
        Your account
      </Link>
    </main>
  );
}
