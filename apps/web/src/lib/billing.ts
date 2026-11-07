import type { Locale } from '@/i18n/config';
import { getApi } from '@/lib/api';

/** Sends the browser to Stripe's checkout page. Card details are typed there, never on CareerFit. */
export async function goToCheckout(
  purchase: { kind: 'pro' } | { kind: 'report'; analysisId: string },
  locale: Locale,
): Promise<void> {
  const { url } = await getApi().billing.checkout(purchase, locale);
  window.location.assign(url);
}

/** Stripe's customer portal: change card, see invoices, cancel. */
export async function goToBillingPortal(locale: Locale): Promise<void> {
  const { url } = await getApi().billing.portal(locale);
  window.location.assign(url);
}
