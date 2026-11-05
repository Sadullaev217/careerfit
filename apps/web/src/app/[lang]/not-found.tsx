'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { useI18n } from '@/i18n/provider';

export default function NotFound() {
  const { t, path } = useI18n();
  return (
    <main className="mx-auto flex w-full max-w-lg grow flex-col items-start justify-center gap-4 p-6">
      <h1 className="text-2xl font-semibold">{t('notFound.title')}</h1>
      <p className="text-muted-foreground">{t('notFound.body')}</p>
      <Button asChild>
        <Link href={path('/')}>{t('notFound.home')}</Link>
      </Button>
    </main>
  );
}
