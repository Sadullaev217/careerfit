import { Linking } from 'react-native';
import { api } from './api';
import { IN_EXPO_GO } from './notifications';

type Purchases = typeof import('react-native-purchases').default;

/**
 * App Store and Google Play purchases, through RevenueCat. Store rules require in-app purchase for Pro and
 * reports on phones, so the app never sends people to the website to pay.
 *
 * The key is RevenueCat's public app key. A Test Store key only works in development builds: RevenueCat
 * stops release builds that use one on purpose. Store builds get the App Store and Google Play keys.
 */
const API_KEY = process.env.EXPO_PUBLIC_REVENUECAT_API_KEY ?? '';
export const REPORT_PRODUCT = 'careerfit_detailed_report';

export type StoreOutcome = 'pro' | 'restored' | 'nothing' | 'cancelled' | 'failed' | 'unavailable';
export type ReportOutcome = 'bought' | 'cancelled' | 'failed' | 'unavailable';

/** Expo Go has no store module, and a build without a key can't sell anything. */
export function purchasesAvailable(): boolean {
  return !IN_EXPO_GO && API_KEY !== '';
}

let loading: Promise<Purchases | null> | null = null;
let signedInAs: string | null = null;

/** RevenueCat, signed in as this CareerFit account, so the API can check its purchases by the same id. */
async function store(userId: string): Promise<Purchases | null> {
  if (!purchasesAvailable()) return null;
  loading ??= import('react-native-purchases').then((module) => module.default).catch(() => null);
  const purchases = await loading;
  if (!purchases) return null;
  if (signedInAs === null) {
    purchases.configure({ apiKey: API_KEY, appUserID: userId });
  } else if (signedInAs !== userId) {
    await purchases.logIn(userId);
  }
  signedInAs = userId;
  return purchases;
}

function cancelled(error: unknown): boolean {
  return (error as { userCancelled?: boolean | null } | null)?.userCancelled === true;
}

async function planIsPro(): Promise<boolean> {
  await api.billing.syncAppStore();
  return (await api.account.plan()).plan === 'pro';
}

export async function buyPro(userId: string): Promise<StoreOutcome> {
  const purchases = await store(userId);
  if (!purchases) return 'unavailable';
  try {
    const offerings = await purchases.getOfferings();
    const offer = offerings.current?.monthly ?? offerings.current?.availablePackages[0];
    if (!offer) return 'unavailable';
    await purchases.purchasePackage(offer);
  } catch (error) {
    return cancelled(error) ? 'cancelled' : 'failed';
  }
  try {
    return (await planIsPro()) ? 'pro' : 'failed';
  } catch {
    return 'failed';
  }
}

export async function restorePurchases(userId: string): Promise<StoreOutcome> {
  const purchases = await store(userId);
  if (!purchases) return 'unavailable';
  try {
    await purchases.restorePurchases();
    return (await planIsPro()) ? 'restored' : 'nothing';
  } catch {
    return 'failed';
  }
}

/** The store's own page for cancelling or changing the subscription. */
export async function manageSubscription(userId: string): Promise<void> {
  const purchases = await store(userId);
  const url = purchases ? (await purchases.getCustomerInfo()).managementURL : null;
  if (url) await Linking.openURL(url);
}

/** Buys one result's detailed report in the store, then has the API confirm it and unlock that result. */
export async function buyReport(userId: string, analysisId: string): Promise<ReportOutcome> {
  const purchases = await store(userId);
  if (!purchases) return 'unavailable';
  let transactionId: string;
  try {
    const [product] = await purchases.getProducts([REPORT_PRODUCT], purchases.PRODUCT_CATEGORY.NON_SUBSCRIPTION);
    if (!product) return 'unavailable';
    transactionId = (await purchases.purchaseStoreProduct(product)).transaction.transactionIdentifier;
  } catch (error) {
    return cancelled(error) ? 'cancelled' : 'failed';
  }
  try {
    await api.billing.claimAppStoreReport({ analysisId, transactionId });
    return 'bought';
  } catch {
    return 'failed';
  }
}

/** Store builds keep the plan fresh: a store subscription can end without telling the API. */
export async function refreshStorePlan(userId: string): Promise<void> {
  if (!(await store(userId))) return;
  await api.billing.syncAppStore().catch(() => undefined);
}

/** On logging out, so the next person on this phone doesn't inherit the purchases. */
export async function forgetStoreAccount(): Promise<void> {
  if (signedInAs === null || !loading) return;
  const purchases = await loading;
  signedInAs = null;
  await purchases?.logOut().catch(() => undefined);
}
