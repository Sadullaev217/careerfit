'use client';

import { Suspense, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { apiErrorCode, type Me } from '@careerfit/shared';
import { LanguageSwitcher } from '@/components/language-switcher';
import { PlanStatus } from '@/components/plan-status';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useConsent } from '@/hooks/use-consent';
import { usePlan } from '@/hooks/use-plan';
import { useI18n } from '@/i18n/provider';
import { getApi } from '@/lib/api';
import { createClient } from '@/lib/supabase/client';

export default function SettingsPage() {
  const { t, path, date } = useI18n();
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const { plan, failed: planFailed, reload } = usePlan();
  const { consent, reload: reloadConsent } = useConsent();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getApi()
      .account.me()
      .then(setMe)
      .catch(() => setError(t('settings.loadFailed')));
  }, [t]);

  const shownError = error ?? (planFailed ? t('settings.loadFailed') : null);

  async function signOut() {
    await createClient().auth.signOut();
    router.push(path('/'));
    router.refresh();
  }

  async function deleteAccount() {
    setError(null);
    try {
      await getApi().account.delete();
      await createClient().auth.signOut();
      router.push(path('/'));
      router.refresh();
    } catch (err) {
      // Deleting stops billing first; if Stripe can't be reached, the account is kept and says so.
      setError(
        apiErrorCode(err) === 'billing_unavailable'
          ? t('settings.deleteBillingFailed')
          : t('settings.deleteFailed'),
      );
    }
  }

  async function withdrawConsent() {
    setError(null);
    try {
      await getApi().account.withdrawConsent();
      await reloadConsent();
    } catch {
      setError(t('settings.withdrawFailed'));
    }
  }

  const sectionClass = 'flex flex-col gap-3 rounded-lg border bg-card p-5';

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-5">
      <h1 className="text-3xl font-semibold tracking-tight">{t('settings.title')}</h1>

      {shownError && (
        <Alert variant="destructive">
          <AlertDescription>{shownError}</AlertDescription>
        </Alert>
      )}

      <section aria-labelledby="account" className={sectionClass}>
        <h2 id="account" className="text-xl font-semibold">
          {t('settings.account')}
        </h2>
        {me ? (
          <p>{t('settings.signedInAs', { email: me.email ?? me.id })}</p>
        ) : (
          <Skeleton role="status" aria-label={t('common.loading')} className="h-6 w-2/3" />
        )}
        <Button variant="outline" className="self-start" onClick={() => void signOut()}>
          {t('nav.logOut')}
        </Button>
      </section>

      <section aria-labelledby="language" className={sectionClass}>
        <h2 id="language" className="text-xl font-semibold">
          {t('settings.language')}
        </h2>
        <p className="text-sm text-muted-foreground">{t('settings.languageNote')}</p>
        <LanguageSwitcher label={t('settings.chooseLanguage')} />
      </section>

      <section aria-labelledby="subscription" className={sectionClass} data-testid="subscription">
        <h2 id="subscription" className="text-xl font-semibold">
          {t('settings.subscription')}
        </h2>
        <Suspense>
          <PlanStatus plan={plan} reload={reload} />
        </Suspense>
      </section>

      <section aria-labelledby="privacy" className={sectionClass} data-testid="privacy">
        <h2 id="privacy" className="text-xl font-semibold">
          {t('settings.privacyTitle')}
        </h2>
        {consent ? (
          <p>
            {consent.accepted && consent.acceptedAt
              ? t('settings.privacyAccepted', { date: date(consent.acceptedAt) })
              : t('settings.privacyMissing')}
          </p>
        ) : (
          <Skeleton role="status" aria-label={t('common.loading')} className="h-6 w-2/3" />
        )}
        <p className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
          <Link href={path('/privacy')} className="font-medium underline underline-offset-4">
            {t('legal.privacy')}
          </Link>
          <Link href={path('/terms')} className="font-medium underline underline-offset-4">
            {t('legal.terms')}
          </Link>
          <Link
            href={path('/how-scoring-works')}
            className="font-medium underline underline-offset-4"
          >
            {t('legal.howScoreWorks')}
          </Link>
        </p>
        {consent?.accepted && (
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="outline" className="self-start">
                {t('settings.withdrawAction')}
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>{t('settings.withdrawConfirmTitle')}</AlertDialogTitle>
                <AlertDialogDescription>{t('settings.withdrawConfirmBody')}</AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                <AlertDialogAction onClick={() => void withdrawConsent()}>
                  {t('settings.withdrawConfirmAction')}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        )}
      </section>

      <section aria-labelledby="delete" className={sectionClass}>
        <h2 id="delete" className="text-xl font-semibold">
          {t('settings.deleteTitle')}
        </h2>
        <p className="text-sm text-muted-foreground">{t('settings.deleteBody')}</p>
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button variant="destructive" className="self-start">
              {t('settings.deleteAction')}
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>{t('settings.deleteConfirmTitle')}</AlertDialogTitle>
              <AlertDialogDescription>{t('settings.deleteConfirmBody')}</AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
              <AlertDialogAction onClick={() => void deleteAccount()}>
                {t('settings.deleteConfirmAction')}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </section>
    </div>
  );
}
