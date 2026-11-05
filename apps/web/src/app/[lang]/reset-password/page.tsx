'use client';

import { useState, type FormEvent } from 'react';
import Link from 'next/link';
import { LanguageSwitcher } from '@/components/language-switcher';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useI18n } from '@/i18n/provider';
import type { TextKey } from '@/i18n/translate';
import { createClient } from '@/lib/supabase/client';

const MIN_PASSWORD_LENGTH = 8;

/** Where the emailed reset link lands, already signed in by the link itself. */
export default function ResetPasswordPage() {
  const { t, path } = useI18n();
  const [password, setPassword] = useState('');
  const [failure, setFailure] = useState<TextKey | null>(null);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setFailure(null);
    const { error } = await createClient().auth.updateUser({ password });
    if (!error) setSaved(true);
    else if (error.code === 'same_password') setFailure('resetPassword.samePassword');
    else if (error.code === 'weak_password') setFailure('login.weakPassword');
    else setFailure('resetPassword.failed');
    setBusy(false);
  }

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
        <div className="flex w-full max-w-sm flex-col gap-5 rounded-lg border bg-card p-6 shadow-sm">
          <h1 className="text-2xl font-semibold">{t('resetPassword.title')}</h1>
          {saved ? (
            <>
              <Alert role="status">
                <AlertDescription>{t('resetPassword.done')}</AlertDescription>
              </Alert>
              <Button asChild>
                <Link href={path('/analyses')}>{t('resetPassword.continue')}</Link>
              </Button>
            </>
          ) : (
            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="new-password">{t('resetPassword.password')}</Label>
                <Input
                  id="new-password"
                  type="password"
                  autoComplete="new-password"
                  required
                  minLength={MIN_PASSWORD_LENGTH}
                  aria-describedby="new-password-hint"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                <p id="new-password-hint" className="text-sm text-muted-foreground">
                  {t('login.passwordHint', { count: MIN_PASSWORD_LENGTH })}
                </p>
              </div>
              {failure && (
                <Alert variant="destructive">
                  <AlertDescription>{t(failure)}</AlertDescription>
                </Alert>
              )}
              {failure === 'resetPassword.failed' && (
                <Button asChild variant="link" className="-mt-2 h-8 self-start px-0">
                  <Link href={path('/login?mode=reset')}>{t('resetPassword.newLink')}</Link>
                </Button>
              )}
              <Button type="submit" disabled={busy}>
                {t('resetPassword.submit')}
              </Button>
            </form>
          )}
        </div>
      </main>
    </div>
  );
}
