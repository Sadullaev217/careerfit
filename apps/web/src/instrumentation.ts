import * as Sentry from '@sentry/nextjs';

import { sentryOptions } from '@/lib/error-reports';

export function register() {
  // Server-side rendering errors. SENTRY_DSN may differ from the browser's NEXT_PUBLIC_SENTRY_DSN.
  Sentry.init(sentryOptions(process.env.SENTRY_DSN ?? process.env.NEXT_PUBLIC_SENTRY_DSN));
}

export const onRequestError = Sentry.captureRequestError;
