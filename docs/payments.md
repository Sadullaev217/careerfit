# Payments

CareerFit has two plans and one extra:

|                 | Price (CAD)     | Includes                                                                        |
| --------------- | --------------- | ------------------------------------------------------------------------------- |
| Free            | —               | One analysis a calendar month (UTC), the full report and plan, all past results |
| Pro             | 4.99 a month    | Unlimited analyses, resume lines rewritten for each job, the progress view      |
| Detailed report | 2.99 per result | A PDF of one finished result, on any plan                                       |

Prices live in Stripe and RevenueCat; `PRICES` in `packages/shared` only shows them before checkout.

## Where the rules are enforced

Everything is decided on the server. Apps only show what the API says.

- **The monthly limit.** `POST /analyses` checks the count quickly, then the database function
  `start_analysis_within_limit` checks again and creates the analysis under a per-person lock, so two
  requests at once can't both pass. Failed analyses don't count. At the limit the API answers
  `402 limit_reached`.
- **Pro features** answer `402 pro_required` on the free plan. Tailored lines made while on Pro stay
  readable afterwards.
- **The PDF** answers `402 report_not_purchased` unless that result's report was bought.
- `GET /account/plan` returns the plan, usage, limit, reset day, renewal or end date and bought reports.

## Web: Stripe

People pay on Stripe's own pages, so card details never reach CareerFit.

| Step                | How                                                                                                                                                     |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Buy Pro or a report | `POST /billing/checkout` creates a Stripe Checkout session (subscription or one-time payment) for the person's Stripe customer, created once and reused |
| Manage or cancel    | `POST /billing/portal` opens Stripe's customer portal: change card, invoices, cancel at the end of the period                                           |
| Keep plans in step  | `POST /billing/stripe-webhook`                                                                                                                          |

The webhook:

- checks Stripe's signature (`STRIPE_WEBHOOK_SECRET`) and rejects anything else with 400;
- handles each event once: event ids are stored in `stripe_events`, and duplicates are skipped;
- re-reads the subscription from Stripe instead of trusting the event's copy, so late or out-of-order
  events can't leave a stale plan. An old subscription ending never undoes a newer one;
- handles `customer.subscription.created`, `.updated` and `.deleted`, `invoice.paid`,
  `invoice.payment_failed` and `checkout.session.completed` (Pro, or a paid report);
- returns 500 if something fails midway, without marking the event handled, so Stripe sends it again.

**Statuses.** `active` and `trialing` are Pro. After a failed payment Stripe keeps the subscription
`past_due` while it retries; Pro continues and Settings asks for a new card. When Stripe gives up
(`canceled` or `unpaid`), the account is free again.

**Deleting an account** deletes the Stripe customer first, which cancels any subscription at once and
removes the email from Stripe. If Stripe can't be reached, nothing is deleted and the person is told.

## Phones: in-app purchase through RevenueCat

The App Store and Google Play require their own in-app purchase for digital subscriptions and unlocks,
and outside the US the app may not point people to the website to pay (App Store guideline 3.1.1). A
service that also works on the web must offer the same things as in-app purchases (3.1.3(b)). So the app
sells Pro and reports through the stores and never links to Stripe.

**Approach chosen: RevenueCat** (`react-native-purchases`), rather than StoreKit and Play Billing directly.

|                                  | RevenueCat                                                                | Native StoreKit 2 + Play Billing                                                     |
| -------------------------------- | ------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| Code                             | One library for both stores, with an Expo-compatible module               | Two store APIs, plus our own receipt checks for each                                 |
| Server check                     | One REST call per account                                                 | Apple's App Store Server API and Google's Play Developer API, each with its own keys |
| Renewals, refunds, grace periods | Normalised into one entitlement                                           | Our code, per store                                                                  |
| Testing                          | Test Store: test purchases without App Store or Play accounts             | Sandbox accounts on both stores, which need the paid developer accounts              |
| Cost                             | Free for small apps, then a share of revenue (see revenuecat.com/pricing) | No fee                                                                               |

For a small team that still has no store accounts, RevenueCat is the clear fit; moving to native later
only changes `apps/mobile/src/lib/purchases.ts` and `apps/api/app/revenuecat.py`.

How it works:

1. The app signs in to RevenueCat with the CareerFit user id, the same id the API knows.
2. Pro: the app buys the current offering's monthly package. Report: it buys the
   `careerfit_detailed_report` product.
3. The app then asks the API to check: `POST /billing/app-store/sync` (Pro) or
   `POST /billing/app-store/report` with the transaction id (report).
4. The API asks RevenueCat's server about that user id (REST v1 `GET /subscribers/{id}`, secret key
   on the server only). It never takes the app's word. Pro needs the active `pro` entitlement; a report
   needs a matching purchase, and each purchase unlocks one result only.

RevenueCat webhooks need a public address, so until deployment (Part 12) a store plan lasts until the
expiry RevenueCat reported, and the app re-checks when Settings opens. A Stripe plan is never changed by
a store check, and a store plan never by a Stripe event.

## Setting up

API (`apps/api/.env`):

| Variable                | What                                                                                                                                              |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `STRIPE_SECRET_KEY`     | Stripe test-mode secret key. Then run `uv run --extra dev python -m scripts.stripe_setup` once to create the products, prices and portal settings |
| `STRIPE_WEBHOOK_SECRET` | From `stripe listen --forward-to localhost:8000/billing/stripe-webhook` locally, or the webhook endpoint in the Stripe dashboard                  |
| `WEB_URL`               | Where Stripe sends people back to                                                                                                                 |
| `REVENUECAT_SECRET_KEY` | RevenueCat secret API key                                                                                                                         |

App (`apps/mobile/.env`, and the EAS environment for builds):

| Variable                         | What                                                                         |
| -------------------------------- | ---------------------------------------------------------------------------- |
| `EXPO_PUBLIC_REVENUECAT_API_KEY` | RevenueCat public app key. A Test Store key works only in development builds |

RevenueCat project: entitlement `pro`; products `careerfit_pro_monthly` (monthly subscription, attached to
`pro` and to the current offering) and `careerfit_detailed_report` (one-time).

## Testing

- Stripe test cards: `4242 4242 4242 4242` succeeds; `4000 0000 0000 0341` attaches but fails later,
  for `invoice.payment_failed`. Any future date and any CVC.
- `stripe trigger` sends sample events; real test purchases are better because they carry our metadata.
- RevenueCat Test Store purchases show a dialog to choose success, failure or cancel. Test subscriptions
  renew every 5 minutes and end after about 25.
