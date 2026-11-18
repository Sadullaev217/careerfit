import { Notice } from '@/components/ui';
import { useI18n } from '@/i18n';

/** Set in the EAS environment of the public demo's builds. */
export const DEMO_APP = process.env.EXPO_PUBLIC_DEMO_MODE === 'true';

/** What the public demo is and what not to upload, on the login and Documents screens. */
export function DemoNotice() {
  const { t } = useI18n();
  if (!DEMO_APP) return null;
  return <Notice>{t('demo.banner')}</Notice>;
}
