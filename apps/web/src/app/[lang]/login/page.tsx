'use client';

import { Suspense, useEffect, useRef, useState, type FormEvent } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { LanguageSwitcher } from '@/components/language-switcher';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { useI18n } from '@/i18n/provider';
import type { TextKey } from '@/i18n/translate';
import { createClient } from '@/lib/supabase/client';

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const SUPABASE_KEY = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
const configured = Boolean(SUPABASE_URL && SUPABASE_KEY);
const MIN_PASSWORD_LENGTH = 8;
const SOCIAL_PROVIDERS = ['google', 'apple'] as const;

type SocialProvider = (typeof SOCIAL_PROVIDERS)[number];
type Mode = 'signin' | 'signup' | 'reset';

const MODE_TEXT: Record<Mode, { title: TextKey; submit: TextKey; switchTo: TextKey }> = {
  signin: {
    title: 'login.titleSignIn',
    submit: 'login.submitSignIn',
    switchTo: 'login.switchToSignUp',
  },
  signup: {
    title: 'login.titleSignUp',
    submit: 'login.submitSignUp',
    switchTo: 'login.switchToSignIn',
  },
  reset: {
    title: 'login.titleReset',
    submit: 'login.submitReset',
    switchTo: 'login.backToSignIn',
  },
};

/** Failures worth explaining. Every other code keeps the general message for what was being done. */
const ERROR_TEXT: Record<string, TextKey> = {
  over_email_send_rate_limit: 'login.tooManyEmails',
  email_address_not_authorized: 'login.emailNotAllowed',
  weak_password: 'login.weakPassword',
};

function startingMode(value: string | null): Mode {
  return value === 'signup' || value === 'reset' ? value : 'signin';
}

function callbackUrl() {
  return `${window.location.origin}/auth/callback`;
}

/** A sign-in method that isn't turned on for this project ends on a raw error page, so it isn't offered. */
function useSocialProviders(): SocialProvider[] {
  const [providers, setProviders] = useState<SocialProvider[]>([]);

  useEffect(() => {
    if (!SUPABASE_URL || !SUPABASE_KEY) return;
    let active = true;
    fetch(`${SUPABASE_URL}/auth/v1/settings`, { headers: { apikey: SUPABASE_KEY } })
      .then((response) => (response.ok ? response.json() : null))
      .then((settings: { external?: Record<string, boolean> } | null) => {
        if (active) setProviders(SOCIAL_PROVIDERS.filter((name) => settings?.external?.[name]));
      })
      // Email sign-in still works without this list.
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

  return providers;
}

function LoginForm() {
  const { t, path } = useI18n();
  const router = useRouter();
  const search = useSearchParams();
  const providers = useSocialProviders();
  const emailInput = useRef<HTMLInputElement>(null);
  const [mode, setMode] = useState<Mode>(startingMode(search.get('mode')));
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [message, setMessage] = useState<string | null>(
    search.get('error') ? t('login.callbackFailed') : configured ? null : t('login.notConfigured'),
  );
  const [notice, setNotice] = useState<string | null>(null);
  // Kept apart from the email box, so editing the box can't send the link somewhere else.
  const [awaitingConfirmation, setAwaitingConfirmation] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function errorText(code: string | undefined, fallback: TextKey) {
    return t((code && ERROR_TEXT[code]) || fallback);
  }

  function clearMessages() {
    setMessage(null);
    setNotice(null);
    setAwaitingConfirmation(null);
  }

  function changeMode(next: Mode) {
    setMode(next);
    clearMessages();
  }

  async function signIn() {
    const { error } = await createClient().auth.signInWithPassword({ email, password });
    if (!error) {
      router.push(path('/analyses'));
    } else if (error.code === 'email_not_confirmed') {
      setMessage(t('login.notConfirmed'));
      setAwaitingConfirmation(email);
    } else {
      setMessage(t('login.failed'));
    }
  }

  async function signUp() {
    const { data, error } = await createClient().auth.signUp({
      email,
      password,
      options: { emailRedirectTo: callbackUrl() },
    });
    if (error) {
      setMessage(errorText(error.code, 'login.signupFailed'));
    } else if (data.session) {
      router.push(path('/analyses'));
    } else {
      // Supabase gives this same answer for an email that already has an account, and sends
      // nothing. The notice covers both cases, so that typing someone's email here doesn't
      // reveal whether they use CareerFit.
      setNotice(t('login.checkEmail', { email }));
      setAwaitingConfirmation(email);
    }
  }

  async function sendResetLink() {
    const { error } = await createClient().auth.resetPasswordForEmail(email, {
      redirectTo: callbackUrl(),
    });
    if (error) setMessage(errorText(error.code, 'login.resetFailed'));
    else setNotice(t('login.resetSent', { email }));
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    clearMessages();
    const submit = { signin: signIn, signup: signUp, reset: sendResetLink }[mode];
    await submit();
    setBusy(false);
  }

  async function resendConfirmation(address: string) {
    setBusy(true);
    setMessage(null);
    setNotice(null);
    const { error } = await createClient().auth.resend({
      type: 'signup',
      email: address,
      options: { emailRedirectTo: callbackUrl() },
    });
    if (error) setMessage(errorText(error.code, 'login.resendFailed'));
    else setNotice(t('login.resent', { email: address }));
    setBusy(false);
  }

  async function handleOAuth(provider: SocialProvider) {
    const { error } = await createClient().auth.signInWithOAuth({
      provider,
      options: { redirectTo: callbackUrl() },
    });
    if (error) setMessage(t('login.failed'));
  }

  const text = MODE_TEXT[mode];

  return (
    <div className="flex w-full max-w-sm flex-col gap-5 rounded-lg border bg-card p-6 shadow-sm">
      <div className="flex flex-col gap-1.5">
        <h1 className="text-2xl font-semibold">{t(text.title)}</h1>
        {mode === 'reset' && (
          <p className="text-sm text-muted-foreground">{t('login.resetIntro')}</p>
        )}
      </div>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="email">{t('login.email')}</Label>
          <Input
            ref={emailInput}
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        {mode !== 'reset' && (
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="password">{t('login.password')}</Label>
            <Input
              id="password"
              type="password"
              autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
              required
              // Only new passwords follow this rule. An older account may have a shorter one.
              minLength={mode === 'signup' ? MIN_PASSWORD_LENGTH : undefined}
              aria-describedby={mode === 'signup' ? 'password-hint' : undefined}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            {mode === 'signup' && (
              <p id="password-hint" className="text-sm text-muted-foreground">
                {t('login.passwordHint', { count: MIN_PASSWORD_LENGTH })}
              </p>
            )}
            {mode === 'signin' && (
              <Button
                type="button"
                variant="link"
                className="h-8 self-start px-0"
                onClick={() => {
                  changeMode('reset');
                  // This button is about to disappear, and focus shouldn't vanish with it.
                  emailInput.current?.focus();
                }}
              >
                {t('login.forgot')}
              </Button>
            )}
          </div>
        )}
        {message && (
          <Alert variant="destructive">
            <AlertDescription className="wrap-anywhere">{message}</AlertDescription>
          </Alert>
        )}
        {notice && (
          <Alert role="status">
            <AlertDescription className="wrap-anywhere whitespace-pre-line">{notice}</AlertDescription>
          </Alert>
        )}
        {awaitingConfirmation && (
          <Button
            type="button"
            variant="link"
            className="-mt-2 h-8 self-start px-0"
            disabled={busy}
            onClick={() => void resendConfirmation(awaitingConfirmation)}
          >
            {t('login.resend')}
          </Button>
        )}
        <Button type="submit" disabled={busy || !configured}>
          {t(text.submit)}
        </Button>
      </form>
      {mode !== 'reset' && providers.length > 0 && (
        <>
          <div className="flex items-center gap-3">
            <Separator className="shrink" />
            <span className="text-sm text-muted-foreground">{t('login.or')}</span>
            <Separator className="shrink" />
          </div>
          <div className="flex flex-col gap-2">
            {providers.map((provider) => (
              <Button key={provider} variant="outline" onClick={() => void handleOAuth(provider)}>
                {t(`login.${provider}`)}
              </Button>
            ))}
          </div>
        </>
      )}
      <Button
        variant="link"
        className="h-auto whitespace-normal p-0"
        onClick={() => changeMode(mode === 'signin' ? 'signup' : 'signin')}
      >
        {t(text.switchTo)}
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
