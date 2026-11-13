'use client';

import { useState } from 'react';
import { Check } from 'lucide-react';
import { PRICES } from '@careerfit/shared';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { usePlan } from '@/hooks/use-plan';
import { useI18n } from '@/i18n/provider';
import type { TextKey } from '@/i18n/translate';
import { apiErrorText } from '@/lib/api-error';
import { goToBillingPortal, goToCheckout } from '@/lib/billing';

function Features({ items }: { items: TextKey[] }) {
  const { t } = useI18n();
  return (
    <ul className="flex flex-col gap-2">
      {items.map((item) => (
        <li key={item} className="flex items-start gap-2">
          <Check aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-shown" />
          {t(item)}
        </li>
      ))}
    </ul>
  );
}

export default function PricingPage() {
  const i18n = useI18n();
  const { t, price, locale } = i18n;
  const { plan } = usePlan();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isPro = plan?.plan === 'pro';

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

  const card = 'flex flex-col gap-4 rounded-lg border bg-card p-6';

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold tracking-tight">{t('pricing.title')}</h1>
        <p className="text-muted-foreground">{t('pricing.intro')}</p>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="grid gap-4 md:grid-cols-3">
        <section aria-labelledby="plan-free" className={card} data-testid="plan-free">
          <div className="flex items-center justify-between gap-2">
            <h2 id="plan-free" className="text-xl font-semibold">
              {t('pricing.free')}
            </h2>
            {plan && !isPro && <Badge variant="secondary">{t('pricing.current')}</Badge>}
          </div>
          <p className="text-2xl font-semibold">{t('pricing.freePrice')}</p>
          <Features items={['pricing.freeItem1', 'pricing.freeItem2', 'pricing.freeItem3', 'pricing.freeItem4']} />
        </section>

        <section aria-labelledby="plan-pro" className={`${card} border-primary`} data-testid="plan-pro">
          <div className="flex items-center justify-between gap-2">
            <h2 id="plan-pro" className="text-xl font-semibold">
              {t('pricing.pro')}
            </h2>
            {isPro && <Badge>{t('pricing.current')}</Badge>}
          </div>
          <p className="text-2xl font-semibold">
            {t('pricing.proPrice', { price: price(PRICES.proMonthly, PRICES.currency) })}
          </p>
          <Features items={['pricing.proItem1', 'pricing.proItem2']} />
          <div className="mt-auto">
            {!plan ? (
              <Skeleton className="h-9 w-40" />
            ) : isPro ? (
              plan.provider === 'stripe' && (
                <Button variant="outline" disabled={busy} onClick={() => void open(() => goToBillingPortal(locale))}>
                  {t('billing.manage')}
                </Button>
              )
            ) : (
              <Button disabled={busy} onClick={() => void open(() => goToCheckout({ kind: 'pro' }, locale))}>
                {busy ? t('billing.opening') : t('billing.upgrade')}
              </Button>
            )}
          </div>
        </section>

        <section aria-labelledby="plan-report" className={card} data-testid="plan-report">
          <h2 id="plan-report" className="text-xl font-semibold">
            {t('pricing.report')}
          </h2>
          <p className="text-2xl font-semibold">
            {t('pricing.reportPrice', { price: price(PRICES.report, PRICES.currency) })}
          </p>
          <p className="text-muted-foreground">{t('pricing.reportBody')}</p>
        </section>
      </div>

      <div className="flex flex-col gap-1 text-sm text-muted-foreground">
        <p>{t('pricing.smallPrint')}</p>
        <p>{t('pricing.testMode')}</p>
      </div>
    </div>
  );
}
