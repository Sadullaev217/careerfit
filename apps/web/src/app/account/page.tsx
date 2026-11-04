'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { createApiClient, type Me } from '@careerfit/shared';
import { createClient } from '@/lib/supabase/client';

const buttonClass = 'rounded border border-zinc-400 p-2 font-medium';

function getApi() {
  const supabase = createClient();
  return createApiClient(
    process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000',
    async () => (await supabase.auth.getSession()).data.session?.access_token,
  );
}

export default function AccountPage() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getApi()
      .account.me()
      .then(setMe)
      .catch(() => setError('Could not load your account.'));
  }, []);

  async function signOut() {
    await createClient().auth.signOut();
    router.push('/login');
  }

  async function deleteAccount() {
    if (!window.confirm('Permanently delete your account and all your data?')) return;
    try {
      await getApi().account.delete();
      await createClient().auth.signOut({ scope: 'local' });
      router.push('/');
    } catch {
      setError('Could not delete your account. Please try again.');
    }
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-sm flex-col justify-center gap-4 p-6">
      <h1 className="text-2xl font-semibold">Your account</h1>
      {me && <p>Signed in as {me.email ?? me.id}</p>}
      {error && <p role="alert">{error}</p>}
      <button className={buttonClass} onClick={signOut}>
        Log out
      </button>
      <button className={`${buttonClass} text-red-600`} onClick={deleteAccount}>
        Delete account
      </button>
    </main>
  );
}
