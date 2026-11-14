import * as Sentry from '@sentry/nextjs';
import posthog from 'posthog-js';

import { sentryOptions } from '@/lib/error-reports';

// Both stay off unless their keys are set, so local runs and tests send nothing.
try {
  Sentry.init(sentryOptions(process.env.NEXT_PUBLIC_SENTRY_DSN));
} catch {
  // Error reporting must never stop the app from starting.
}

const POSTHOG_TOKEN = process.env.NEXT_PUBLIC_POSTHOG_TOKEN;
if (POSTHOG_TOKEN) {
  try {
    posthog.init(POSTHOG_TOKEN, {
      api_host: process.env.NEXT_PUBLIC_POSTHOG_HOST ?? 'https://eu.i.posthog.com',
      // No cookies or local storage, so no cookie banner: each visit counts as a new visitor.
      persistence: 'memory',
      person_profiles: 'never',
      // Page views only. Clicks, form fields and screen recordings could capture resume text.
      capture_pageview: 'history_change',
      autocapture: false,
      disable_session_recording: true,
      disable_surveys: true,
      // Query strings can carry sign-in codes.
      before_send: (event) => {
        if (event?.properties?.$current_url) {
          event.properties.$current_url = String(event.properties.$current_url).split(/[?#]/)[0];
        }
        return event;
      },
    });
  } catch {
    // Analytics must never stop the app from starting.
  }
}
