'use client';

import { Button } from '@/components/ui/button';
import { useI18n } from '@/i18n/provider';

export default function ErrorPage({ reset }: { reset: () => void }) {
  const { t } = useI18n();
  return (
    <main className="mx-auto flex w-full max-w-lg grow flex-col items-start justify-center gap-4 p-6">
      <h1 className="text-2xl font-semibold">{t('errors.pageTitle')}</h1>
      <p className="text-muted-foreground">{t('errors.pageBody')}</p>
      <Button onClick={reset}>{t('common.tryAgain')}</Button>
    </main>
  );
}
