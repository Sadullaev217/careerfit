import { randomUUID } from 'node:crypto';

/**
 * Throwaway accounts for the tests, made and removed through Supabase's admin API. The secret key
 * comes from the environment and is never printed. Only for a local or test Supabase project.
 */
const SUPABASE_URL = process.env.E2E_SUPABASE_URL ?? '';
const SECRET_KEY = process.env.E2E_SUPABASE_SECRET_KEY ?? '';

export const accountsAvailable = Boolean(SUPABASE_URL && SECRET_KEY);

export type TestAccount = { id: string; email: string; password: string };

function adminHeaders() {
  return {
    apikey: SECRET_KEY,
    Authorization: `Bearer ${SECRET_KEY}`,
    'Content-Type': 'application/json',
  };
}

export async function createAccount(): Promise<TestAccount> {
  const email = `e2e-${randomUUID()}@example.com`;
  const password = randomUUID();
  const response = await fetch(`${SUPABASE_URL}/auth/v1/admin/users`, {
    method: 'POST',
    headers: adminHeaders(),
    body: JSON.stringify({ email, password, email_confirm: true }),
  });
  if (!response.ok) throw new Error(`Could not create a test account: HTTP ${response.status}`);
  const user = (await response.json()) as { id: string };
  return { id: user.id, email, password };
}

/** True when the account no longer exists. */
export async function accountIsGone(id: string): Promise<boolean> {
  const response = await fetch(`${SUPABASE_URL}/auth/v1/admin/users/${id}`, {
    headers: adminHeaders(),
  });
  return response.status === 404;
}

export async function deleteAccount(id: string): Promise<void> {
  await fetch(`${SUPABASE_URL}/auth/v1/admin/users/${id}`, {
    method: 'DELETE',
    headers: adminHeaders(),
  });
}
