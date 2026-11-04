'use client';

import { useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { createClient } from '@/lib/supabase/client';

const configured = Boolean(
  process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
);

const inputClass = 'rounded border border-zinc-400 bg-transparent p-2';
const buttonClass = 'rounded border border-zinc-400 p-2 font-medium disabled:opacity-50';

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<'signin' | 'signup'>('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [message, setMessage] = useState<string | null>(
    configured ? null : 'Sign-in is not configured yet.',
  );
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    const supabase = createClient();
    if (mode === 'signin') {
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) setMessage(error.message);
      else router.push('/account');
    } else {
      const { data, error } = await supabase.auth.signUp({
        email,
        password,
        options: { emailRedirectTo: `${window.location.origin}/auth/callback` },
      });
      if (error) setMessage(error.message);
      else if (data.session) router.push('/account');
      else setMessage('Check your email to confirm your account.');
    }
    setBusy(false);
  }

  async function handleOAuth(provider: 'google' | 'apple') {
    const { error } = await createClient().auth.signInWithOAuth({
      provider,
      options: { redirectTo: `${window.location.origin}/auth/callback` },
    });
    if (error) setMessage(error.message);
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-sm flex-col justify-center gap-4 p-6">
      <h1 className="text-2xl font-semibold">
        {mode === 'signin' ? 'Log in to CareerFit' : 'Create your account'}
      </h1>
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <label className="flex flex-col gap-1">
          Email
          <input
            className={inputClass}
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>
        <label className="flex flex-col gap-1">
          Password
          <input
            className={inputClass}
            type="password"
            autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        <button className={buttonClass} type="submit" disabled={busy || !configured}>
          {mode === 'signin' ? 'Log in' : 'Sign up'}
        </button>
      </form>
      <button className={buttonClass} disabled={!configured} onClick={() => handleOAuth('google')}>
        Continue with Google
      </button>
      <button className={buttonClass} disabled={!configured} onClick={() => handleOAuth('apple')}>
        Continue with Apple
      </button>
      <button
        className="underline"
        onClick={() => setMode(mode === 'signin' ? 'signup' : 'signin')}
      >
        {mode === 'signin' ? 'Need an account? Sign up' : 'Have an account? Log in'}
      </button>
      {message && <p role="alert">{message}</p>}
    </main>
  );
}
