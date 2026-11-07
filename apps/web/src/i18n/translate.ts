import type en from './en.json';
import type { Locale } from './config';

export type Dictionary = typeof en;

type Plural = { one: string; other: string; few?: string; many?: string };

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
  return template.replace(/\{(\w+)\}/g, (match, name: string) =>
    name in values ? String(values[name]) : match,
  );
}

/** A plain date means that day where the reader is. Read as UTC, it shows the day before in Canada. */
function parseDate(value: string | Date): Date {
  if (typeof value !== 'string') return value;
  const plain = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  return plain ? new Date(Number(plain[1]), Number(plain[2]) - 1, Number(plain[3])) : new Date(value);
}

export function createTranslator(locale: Locale, dict: Dictionary) {
  const rules = new Intl.PluralRules(locale);
  return {
    t(key: TextKey, values?: Values): string {
      return fill(lookup(dict, key) as string, values);
    },
    /** Russian has more plural forms than English, so counts can't be built by adding an "s". */
    plural(key: PluralKey, count: number, values?: Values): string {
      const forms = lookup(dict, key) as Plural;
      const form = forms[rules.select(count) as keyof Plural] ?? forms.other;
      return fill(form, { count, ...values });
    },
    /** For keys built from server values, like an error code, which may have no translation. */
    maybe(key: string): string | null {
      const found = lookup(dict, key);
      return typeof found === 'string' ? found : null;
    },
    number(value: number): string {
      return new Intl.NumberFormat(locale === 'ru' ? 'ru-RU' : 'en-CA').format(value);
    },
    money(value: number, currency = 'CAD'): string {
      return new Intl.NumberFormat(locale === 'ru' ? 'ru-RU' : 'en-CA', {
        style: 'currency',
        currency,
        maximumFractionDigits: 0,
      }).format(value);
    },
    /** A price with its cents, unlike money(), which rounds salaries to whole dollars. */
    price(value: number, currency = 'CAD'): string {
      return new Intl.NumberFormat(locale === 'ru' ? 'ru-RU' : 'en-CA', {
        style: 'currency',
        currency,
        minimumFractionDigits: 2,
      }).format(value);
    },
    date(value: string | Date): string {
      return new Intl.DateTimeFormat(locale === 'ru' ? 'ru-RU' : 'en-CA', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      }).format(parseDate(value));
    },
    path(route: string): string {
      return `/${locale}${route === '/' ? '' : route}`;
    },
  };
}

export type Translator = ReturnType<typeof createTranslator>;
