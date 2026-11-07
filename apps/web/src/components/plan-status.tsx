'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import type { PlanInfo } from '@careerfit/shared';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { waitForPlan } from '@/hooks/use-plan';
import { useI18n } from '@/i18n/provider';
import { apiErrorText } from '@/lib/api-error';
import { goToBillingPortal, goToCheckout } from '@/lib/billing';

type Props = {
  plan: PlanInfo | null;
  reload: () => Promise<PlanInfo | null>;
};

/** The Settings section for the plan: what it includes now, what's used, and the ways to change it. */
export function PlanStatus({ plan, reload }: Props) {
  const i18n = useI18n();
  const { t, plural, date, path, locale } = i18n;
  const search = useSearchParams();
  const returning = search.get('checkout') === 'pro';
  const [waiting, setWaiting] = useState<'checking' | 'slow' | 'done' | null>(returning ? 'checking' : null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);

  // Back from Stripe's checkout: the plan changes once Stripe's event reaches the API.
  useEffect(() => {
    if (!returning || started.current) return;
    started.current = true;
    void waitForPlan(reload, (next) => next.plan === 'pro').then((ok) => setWaiting(ok ? 'done' : 'slow'));
  }, [returning, reload]);

  async function open(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (err) {
      setError(apiErrorText(i18n, err, 'billing.checkoutFailed'));
      setBusy(false);
    }
  }

  if (!plan) {
    return <Skeleton role="status" aria-label={t('common.loading')} className="h-20 w-full" />;
  }

  const isPro = plan.plan === 'pro';
  const fromApp = plan.provider === 'revenuecat';

  return (
    <div className="flex flex-col gap-3" data-testid="plan-status">
      {waiting === 'checking' && (
        <Alert role="status">
          <Loader2 aria-hidden="true" className="size-4 animate-spin" />
          <AlertDescription>{t('billing.proStarting')}</AlertDescription>
        </Alert>
      )}
      {waiting === 'done' && (
        <Alert role="status">
          <AlertDescription>{t('billing.proActive')}</AlertDescription>
        </Alert>
      )}
      {waiting === 'slow' && (
        <Alert>
          <AlertDescription>{t('billing.proSlow')}</AlertDescription>
        </Alert>
      )}

      <div className="flex items-center gap-2">
        <span>{t('settings.currentPlan')}</span>
        <Badge variant={isPro ? 'default' : 'secondary'}>
          {isPro ? t('billing.planPro') : t('billing.planFree')}
        </Badge>
      </div>

      {isPro ? (
        <p>
          {t('billing.unlimited')}{' '}
          {plan.currentPeriodEnd &&
            (plan.cancelAtPeriodEnd
              ? t('billing.ends', { date: date(plan.currentPeriodEnd) })
              : t('billing.renews', { date: date(plan.currentPeriodEnd) }))}
        </p>
      ) : (
        <p data-testid="plan-usage">
          {plural('billing.usage', plan.analysesLimit ?? 1, {
            count: plan.analysesUsed,
            limit: plan.analysesLimit ?? 1,
          })}{' '}
          {plan.analysesLimit !== null &&
            plan.analysesUsed >= plan.analysesLimit &&
            t('billing.resets', { date: date(plan.limitResetsAt) })}
        </p>
      )}

      {plan.status === 'past_due' && (
        <Alert variant="destructive">
          <AlertDescription>{t('billing.pastDue')}</AlertDescription>
        </Alert>
      )}

      {fromApp && <p className="text-sm text-muted-foreground">{t('billing.viaApp')}</p>}

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="flex flex-wrap gap-2">
        {!isPro && (
          <Button disabled={busy} onClick={() => void open(() => goToCheckout({ kind: 'pro' }, locale))}>
            {busy ? t('billing.opening') : t('billing.upgrade')}
          </Button>
        )}
        {plan.provider === 'stripe' && (
          <Button variant="outline" disabled={busy} onClick={() => void open(() => goToBillingPortal(locale))}>
            {t('billing.manage')}
          </Button>
        )}
        <Button variant="link" asChild className="px-0">
          <Link href={path('/pricing')}>{t('billing.seePlans')}</Link>
        </Button>
      </div>
    </div>
  );
}
