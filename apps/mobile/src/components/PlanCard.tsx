import { useState } from 'react';
import type { PlanInfo } from '@careerfit/shared';
import { PRICES } from '@careerfit/shared';
import { Badge, Body, Button, Card, Heading, Muted, Notice } from '@/components/ui';
import { useI18n } from '@/i18n';
import { buyPro, manageSubscription, purchasesAvailable, restorePurchases, type StoreOutcome } from '@/lib/purchases';

type Props = {
  plan: PlanInfo | null;
  userId: string | undefined;
  onChanged: () => Promise<unknown>;
};

const OUTCOME_TEXT = {
  failed: 'billing.purchaseFailed',
  unavailable: 'billing.storeUnavailable',
  nothing: 'billing.nothingToRestore',
  restored: 'billing.restored',
  pro: 'billing.proActive',
} as const;

/**
 * The plan in Settings. On phones, Pro is bought through the App Store or Google Play (via RevenueCat), as
 * their rules require; the app never points to the website to buy.
 */
export function PlanCard({ plan, userId, onChanged }: Props) {
  const i18n = useI18n();
  const { t, plural, date, price } = i18n;
  const [busy, setBusy] = useState<'buy' | 'restore' | null>(null);
  const [outcome, setOutcome] = useState<StoreOutcome | null>(null);

  async function run(kind: 'buy' | 'restore') {
    if (!userId) return;
    setBusy(kind);
    setOutcome(null);
    const result = kind === 'buy' ? await buyPro(userId) : await restorePurchases(userId);
    if (result !== 'cancelled') setOutcome(result);
    await onChanged();
    setBusy(null);
  }

  if (!plan) {
    return (
      <Card>
        <Heading>{t('settings.plan')}</Heading>
        <Muted>{t('common.loading')}</Muted>
      </Card>
    );
  }

  const isPro = plan.plan === 'pro';
  const limit = plan.analysesLimit;
  return (
    <Card>
      <Heading>{t('settings.plan')}</Heading>
      <Badge label={isPro ? t('settings.planPro') : t('settings.planFree')} tone={isPro ? 'shown' : 'neutral'} />
      {isPro ? (
        <Body>
          {t('billing.unlimited')}{' '}
          {plan.currentPeriodEnd &&
            (plan.cancelAtPeriodEnd
              ? t('billing.ends', { date: date(plan.currentPeriodEnd) })
              : t('billing.renews', { date: date(plan.currentPeriodEnd) }))}
        </Body>
      ) : (
        limit !== null && (
          <Body>
            {plural('billing.usage', limit, { count: plan.analysesUsed, limit })}{' '}
            {plan.analysesUsed >= limit && t('billing.resets', { date: date(plan.limitResetsAt) })}
          </Body>
        )
      )}
      {plan.status === 'past_due' && <Notice tone="error">{t('billing.pastDue')}</Notice>}
      {outcome && outcome !== 'cancelled' && (
        <Notice tone={outcome === 'failed' || outcome === 'unavailable' ? 'error' : 'info'}>{t(OUTCOME_TEXT[outcome])}</Notice>
      )}

      {plan.provider === 'stripe' && <Muted>{t('billing.managedOnWeb')}</Muted>}
      {!isPro && purchasesAvailable() && (
        <>
          <Muted>{t('billing.proIncludes')}</Muted>
          <Button
            title={t('billing.upgrade', { price: price(PRICES.proMonthly, PRICES.currency) })}
            busy={busy === 'buy'}
            disabled={busy !== null}
            onPress={() => void run('buy')}
          />
        </>
      )}
      {purchasesAvailable() && plan.provider !== 'stripe' && (
        <Button
          variant="secondary"
          title={t('billing.restore')}
          busy={busy === 'restore'}
          disabled={busy !== null}
          onPress={() => void run('restore')}
        />
      )}
      {isPro && plan.provider === 'revenuecat' && (
        <Button
          variant="secondary"
          title={t('billing.manage')}
          onPress={() => void (userId && manageSubscription(userId))}
        />
      )}
      {!purchasesAvailable() && !isPro && <Muted>{t('billing.storeUnavailable')}</Muted>}
    </Card>
  );
}
