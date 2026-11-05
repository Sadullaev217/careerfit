import { apiErrorCode } from '@careerfit/shared';
import type { TextKey, Translator } from '@/i18n/translate';

/** Server messages are in English, so known error codes are shown in the page's own language. */
export function apiErrorText(i18n: Translator, error: unknown, fallback: TextKey): string {
  const code = apiErrorCode(error);
  return (code && i18n.maybe(`errors.api.${code}`)) || i18n.t(fallback);
}
