'use client';

import { Suspense, useState, type FormEvent } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { LanguageSwitcher } from '@/components/language-switcher';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { useI18n } from '@/i18n/provider';
import { createClient } from '@/lib/supabase/client';

const configured = Boolean(
  process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
);
const MIN_PASSWORD_LENGTH = 8;

function LoginForm() {
  const { t, path } = useI18n();
  const router = useRouter();
  const search = useSearchParams();
  const [mode, setMode] = useState<'signin' | 'signup'>(
    search.get('mode') === 'signup' ? 'signup' : 'signin',
  );
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [message, setMessage] = useState<string | null>(
    search.get('error') ? t('login.callbackFailed') : configured ? null : t('login.notConfigured'),
  );
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    setNotice(null);
    const supabase = createClient();
    if (mode === 'signin') {
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) setMessage(t('login.failed'));
      else router.push(path('/analyses'));
    } else {
      const { data, error } = await supabase.auth.signUp({
        email,
        password,
        options: { emailRedirectTo: `${window.location.origin}/auth/callback` },
      });
      if (error) setMessage(t('login.signupFailed'));
      else if (data.session) router.push(path('/analyses'));
      else setNotice(t('login.checkEmail'));
    }
    setBusy(false);
  }

  async function handleOAuth(provider: 'google' | 'apple') {
    const { error } = await createClient().auth.signInWithOAuth({
      provider,
      options: { redirectTo: `${window.location.origin}/auth/callback` },
    });
    if (error) setMessage(t('login.failed'));
  }

  const isSignIn = mode === 'signin';

  return (
    <div className="flex w-full max-w-sm flex-col gap-5 rounded-lg border bg-card p-6 shadow-sm">
      <h1 className="text-2xl font-semibold">{isSignIn ? t('login.titleSignIn') : t('login.titleSignUp')}</h1>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="email">{t('login.email')}</Label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="password">{t('login.password')}</Label>
          <Input
            id="password"
            type="password"
            autoComplete={isSignIn ? 'current-password' : 'new-password'}
            required
            minLength={MIN_PASSWORD_LENGTH}
            aria-describedby={isSignIn ? undefined : 'password-hint'}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {!isSignIn && (
            <p id="password-hint" className="text-sm text-muted-foreground">
              {t('login.passwordHint', { count: MIN_PASSWORD_LENGTH })}
            </p>
          )}
        </div>
        {message && (
          <Alert variant="destructive">
            <AlertDescription>{message}</AlertDescription>
          </Alert>
        )}
        {notice && (
          <Alert role="status">
            <AlertDescription>{notice}</AlertDescription>
          </Alert>
        )}
        <Button type="submit" disabled={busy || !configured}>
          {isSignIn ? t('login.submitSignIn') : t('login.submitSignUp')}
        </Button>
      </form>
      <div className="flex items-center gap-3">
        <Separator className="shrink" />
        <span className="text-sm text-muted-foreground">{t('login.or')}</span>
        <Separator className="shrink" />
      </div>
      <div className="flex flex-col gap-2">
        <Button variant="outline" disabled={!configured} onClick={() => void handleOAuth('google')}>
          {t('login.google')}
        </Button>
        <Button variant="outline" disabled={!configured} onClick={() => void handleOAuth('apple')}>
          {t('login.apple')}
        </Button>
      </div>
      <Button
        variant="link"
        className="h-auto whitespace-normal p-0"
        onClick={() => {
          setMode(isSignIn ? 'signup' : 'signin');
          setMessage(null);
          setNotice(null);
        }}
      >
        {isSignIn ? t('login.switchToSignUp') : t('login.switchToSignIn')}
      </Button>
    </div>
  );
}

export default function LoginPage() {
  const { path } = useI18n();
  return (
    <div className="flex grow flex-col">
      <header className="mx-auto flex w-full max-w-5xl items-center gap-2 px-4 py-3 sm:px-6">
        <Link href={path('/')} className="text-lg font-semibold tracking-tight">
          CareerFit
        </Link>
        <div className="ms-auto">
          <LanguageSwitcher />
        </div>
      </header>
      <main className="flex grow items-start justify-center px-4 py-6 sm:items-center">
        <Suspense>
          <LoginForm />
        </Suspense>
      </main>
    </div>
  );
}
