export const LOCALES = ['en', 'ru'] as const;
export type Locale = (typeof LOCALES)[number];
export const DEFAULT_LOCALE: Locale = 'en';
export const LOCALE_COOKIE = 'careerfit-locale';

export function isLocale(value: string | undefined): value is Locale {
  return LOCALES.includes(value as Locale);
}

/** Picks a language from a saved choice, then the browser's preference. */
export function preferredLocale(saved: string | undefined, acceptLanguage: string | null): Locale {
  if (isLocale(saved)) return saved;
  for (const part of (acceptLanguage ?? '').split(',')) {
    const language = part.split(';')[0]?.trim().slice(0, 2).toLowerCase();
    if (isLocale(language)) return language;
  }
  return DEFAULT_LOCALE;
}
