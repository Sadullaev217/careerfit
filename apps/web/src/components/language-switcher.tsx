'use client';

import { Suspense } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LOCALE_COOKIE, LOCALES, type Locale } from '@/i18n/config';
import { useI18n } from '@/i18n/provider';

const NAMES: Record<Locale, string> = { en: 'English', ru: 'Русский' };
const SHORT_NAMES: Record<Locale, string> = { en: 'EN', ru: 'RU' };
const ONE_YEAR_SECONDS = 60 * 60 * 24 * 365;

function remember(next: Locale) {
  document.cookie = `${LOCALE_COOKIE}=${next}; path=/; max-age=${ONE_YEAR_SECONDS}; samesite=lax`;
}

function LanguageLinks({ rest, label }: { rest: string; label?: string }) {
  const { locale, t } = useI18n();
  return (
    <nav aria-label={label ?? t('nav.language')} className="flex items-center gap-1 text-sm">
      {LOCALES.map((option) => (
        <Link
          key={option}
          href={`/${option}${rest}`}
          lang={option}
          hrefLang={option}
          aria-label={`${SHORT_NAMES[option]} – ${NAMES[option]}`}
          aria-current={option === locale ? 'true' : undefined}
          onClick={() => remember(option)}
          className={
            option === locale
              ? 'inline-flex min-h-10 min-w-10 items-center justify-center rounded-md bg-secondary font-medium'
              : 'inline-flex min-h-10 min-w-10 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground'
          }
        >
          {SHORT_NAMES[option]}
        </Link>
      ))}
    </nav>
  );
}

function LinksForThisPage({ label }: { label?: string }) {
  const { locale } = useI18n();
  const pathname = usePathname();
  return <LanguageLinks rest={pathname.slice(locale.length + 1)} label={label} />;
}

/** The address isn't known while a page with an id in it is prerendered, so this needs its own boundary. */
export function LanguageSwitcher({ label }: { label?: string }) {
  return (
    <Suspense fallback={<LanguageLinks rest="" label={label} />}>
      <LinksForThisPage label={label} />
    </Suspense>
  );
}
