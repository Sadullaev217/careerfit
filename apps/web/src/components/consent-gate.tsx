'use client';

import { useId, useState, type ReactNode } from 'react';
import Link from 'next/link';
import { apiErrorCode, type ConsentStatus } from '@careerfit/shared';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useConsent } from '@/hooks/use-consent';
import { useI18n } from '@/i18n/provider';
import { getApi } from '@/lib/api';

/**
 * Shows the agreement instead of `children` until the person accepts it. Used where CareerFit reads a
 * resume (onboarding, documents, a new analysis); results, Settings and deletion never wait for it.
 * If the agreement can't be loaded, `children` show and the API refuses uploads by itself.
 */
export function ConsentGate({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const { consent, failed, reload } = useConsent();

  if (failed || consent?.accepted) return children;
  if (!consent) {
    return <Skeleton role="status" aria-label={t('common.loading')} className="h-64 w-full" />;
  }
  return <ConsentScreen consent={consent} onAccepted={reload} />;
}

export function ConsentScreen({
  consent,
  onAccepted,
}: {
  consent: ConsentStatus;
  onAccepted: () => Promise<void>;
}) {
  const { t, path } = useI18n();
  const id = useId();
  const [agreedTerms, setAgreedTerms] = useState(false);
  const [agreedAi, setAgreedAi] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function accept() {
    setSaving(true);
    setError(null);
    try {
      await getApi().account.acceptConsent(consent.version);
      await onAccepted();
    } catch (err) {
      if (apiErrorCode(err) === 'consent_outdated') {
        // The policy changed while this was open: show the new version, unticked.
        setAgreedTerms(false);
        setAgreedAi(false);
        setError(t('consent.outdated'));
        await onAccepted();
      } else {
        setError(t('consent.saveFailed'));
      }
    } finally {
      setSaving(false);
    }
  }

  const linkClass = 'font-medium underline underline-offset-4';

  return (
    <section
      aria-labelledby={`${id}-title`}
      className="flex flex-col gap-4 rounded-lg border bg-card p-5"
      data-testid="consent"
    >
      <h2 id={`${id}-title`} className="text-2xl font-semibold tracking-tight">
        {t('consent.title')}
      </h2>
      <p className="text-muted-foreground">{t('consent.intro')}</p>
      <ul className="flex list-disc flex-col gap-2 ps-5">
        <li>
          {t(consent.aiProcessing === 'openrouter' ? 'consent.aiHosted' : 'consent.aiSelfHosted')}
        </li>
        <li>{t('consent.personalDetails')}</li>
        <li>{t('consent.retention')}</li>
        <li>{t('consent.rights')}</li>
        <li>
          {t('consent.estimate')}{' '}
          <Link href={path('/how-scoring-works')} target="_blank" className={linkClass}>
            {t('legal.howScoreWorks')}
          </Link>
        </li>
      </ul>
      <p className="text-sm">
        <Link href={path('/privacy')} target="_blank" className={linkClass}>
          {t('legal.privacy')}
        </Link>
        {' · '}
        <Link href={path('/terms')} target="_blank" className={linkClass}>
          {t('legal.terms')}
        </Link>
      </p>

      <div className="flex flex-col gap-3">
        <label className="flex items-start gap-3">
          <input
            type="checkbox"
            className="mt-1 size-4 shrink-0 accent-primary"
            checked={agreedTerms}
            onChange={(event) => setAgreedTerms(event.target.checked)}
          />
          <span>{t('consent.agreeTerms')}</span>
        </label>
        <label className="flex items-start gap-3">
          <input
            type="checkbox"
            className="mt-1 size-4 shrink-0 accent-primary"
            checked={agreedAi}
            onChange={(event) => setAgreedAi(event.target.checked)}
          />
          <span>{t('consent.agreeAi')}</span>
        </label>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Button
        size="lg"
        className="self-start"
        disabled={!agreedTerms || !agreedAi || saving}
        onClick={() => void accept()}
      >
        {t('consent.accept')}
      </Button>
    </section>
  );
}
