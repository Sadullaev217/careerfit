import type { Breadcrumb, ErrorEvent } from '@sentry/nextjs';

/**
 * Sentry settings shared by the browser and the server. Error reports leave the app, so they keep the
 * error type and stack and drop anything a person typed or uploaded: request bodies, cookies, query
 * strings, user details, and emails, tokens or long numbers inside messages.
 */
const EMAIL = /[\w.+-]+@[\w-]+(\.[\w-]+)+/g;
const TOKEN = /\b(eyJ[\w-]+\.[\w-]+\.[\w-]+|Bearer\s+\S+|sb_[a-z]+_\w+)/g;
const DIGITS = /\d[\d\s().+-]{7,}\d/g;

export function redact(text: string): string {
  return text.replace(EMAIL, '[email]').replace(TOKEN, '[token]').replace(DIGITS, '[number]');
}

function withoutQuery(url: string | undefined): string | undefined {
  return url?.split(/[?#]/)[0];
}

export function scrubEvent(event: ErrorEvent): ErrorEvent {
  delete event.user;
  if (event.request) {
    event.request = { url: withoutQuery(event.request.url), method: event.request.method };
  }
  if (event.message) event.message = redact(event.message);
  for (const exception of event.exception?.values ?? []) {
    if (exception.value) exception.value = redact(exception.value);
  }
  return event;
}

export function scrubBreadcrumb(breadcrumb: Breadcrumb): Breadcrumb | null {
  // Clicks and key presses can name what someone typed; console lines can hold anything.
  if (breadcrumb.category === 'ui.input' || breadcrumb.category === 'console') return null;
  if (breadcrumb.message) breadcrumb.message = redact(breadcrumb.message);
  if (breadcrumb.data) {
    const { url, method, status_code } = breadcrumb.data as Record<string, unknown>;
    breadcrumb.data = {
      url: typeof url === 'string' ? withoutQuery(url) : undefined,
      method,
      status_code,
    };
  }
  return breadcrumb;
}

export function sentryOptions(dsn: string | undefined) {
  return {
    dsn,
    enabled: Boolean(dsn),
    environment: process.env.NEXT_PUBLIC_ENVIRONMENT ?? 'development',
    sendDefaultPii: false,
    tracesSampleRate: 0,
    beforeSend: scrubEvent,
    beforeBreadcrumb: scrubBreadcrumb,
  };
}
