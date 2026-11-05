import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import * as SecureStore from 'expo-secure-store';
import { getLocales } from 'expo-localization';
import { apiErrorCode } from '@careerfit/shared';
import { en, type Dictionary } from './en';
import { ru } from './ru';
import type { Plural } from './types';

export type Locale = 'en' | 'ru';
export const LOCALES: readonly Locale[] = ['en', 'ru'];
export const LOCALE_NAMES: Record<Locale, string> = { en: 'English', ru: 'Русский' };

const DICTIONARIES: Record<Locale, Dictionary> = { en, ru };
const LANGUAGE_KEY = 'careerfit.language';

type Paths<T, Prefix extends string = ''> = {
  [K in keyof T & string]: T[K] extends string
    ? `${Prefix}${K}`
    : T[K] extends Plural
      ? never
      : Paths<T[K], `${Prefix}${K}.`>;
}[keyof T & string];

type PluralPaths<T, Prefix extends string = ''> = {
  [K in keyof T & string]: T[K] extends string
    ? never
    : T[K] extends Plural
      ? `${Prefix}${K}`
      : PluralPaths<T[K], `${Prefix}${K}.`>;
}[keyof T & string];

export type TextKey = Paths<Dictionary>;
export type PluralKey = PluralPaths<Dictionary>;
type Values = Record<string, string | number>;

function lookup(dict: Dictionary, key: string): unknown {
  return key.split('.').reduce<unknown>((node, part) => (node as Record<string, unknown>)?.[part], dict);
}

function fill(template: string, values?: Values): string {
  if (!values) return template;
  return template.replace(/\{(\w+)\}/g, (match, name: string) => (name in values ? String(values[name]) : match));
}

// Written out rather than read from Intl.PluralRules, which the phone's JavaScript engine may not have.
function pluralForm(locale: Locale, count: number): keyof Plural {
  if (locale === 'en') return count === 1 ? 'one' : 'other';
  if (!Number.isInteger(count)) return 'other';
  const lastDigit = count % 10;
  const lastTwo = count % 100;
  if (lastDigit === 1 && lastTwo !== 11) return 'one';
  if (lastDigit >= 2 && lastDigit <= 4 && (lastTwo < 12 || lastTwo > 14)) return 'few';
  return 'many';
}

/** A plain date means that day where the reader is. Read as UTC, it shows the day before in Canada. */
function parseDate(value: string): Date {
  const plain = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  return plain ? new Date(Number(plain[1]), Number(plain[2]) - 1, Number(plain[3])) : new Date(value);
}

export function createTranslator(locale: Locale) {
  const dict = DICTIONARIES[locale];
  const formatLocale = locale === 'ru' ? 'ru-RU' : 'en-CA';
  const t = (key: TextKey, values?: Values): string => fill(lookup(dict, key) as string, values);
  const maybe = (key: string): string | null => {
    const found = lookup(dict, key);
    return typeof found === 'string' ? found : null;
  };
  return {
    locale,
    t,
    maybe,
    plural(key: PluralKey, count: number, values?: Values): string {
      const forms = lookup(dict, key) as Plural;
      return fill(forms[pluralForm(locale, count)] ?? forms.other, { count, ...values });
    },
    /** The API's message for a known error code, in this language, or a general one. */
    errorText(error: unknown, fallback: TextKey): string {
      const code = apiErrorCode(error);
      return (code && maybe(`errors.api.${code}`)) || t(fallback);
    },
    money(value: number, currency = 'CAD'): string {
      return new Intl.NumberFormat(formatLocale, { style: 'currency', currency, maximumFractionDigits: 0 }).format(value);
    },
    date(value: string): string {
      return new Intl.DateTimeFormat(formatLocale, { year: 'numeric', month: 'short', day: 'numeric' }).format(parseDate(value));
    },
  };
}

export type Translator = ReturnType<typeof createTranslator> & { setLocale: (next: Locale) => void };

function deviceLocale(): Locale {
  return getLocales()[0]?.languageCode === 'ru' ? 'ru' : 'en';
}

const I18nContext = createContext<Translator | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(deviceLocale);

  useEffect(() => {
    SecureStore.getItemAsync(LANGUAGE_KEY)
      .then((saved) => {
        if (saved === 'en' || saved === 'ru') setLocaleState(saved);
      })
      .catch(() => undefined);
  }, []);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    SecureStore.setItemAsync(LANGUAGE_KEY, next).catch(() => undefined);
  }, []);

  const value = useMemo(() => ({ ...createTranslator(locale), setLocale }), [locale, setLocale]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): Translator {
  const value = useContext(I18nContext);
  if (!value) throw new Error('useI18n must be used inside I18nProvider');
  return value;
}
