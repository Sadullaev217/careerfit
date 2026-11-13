'use client';

import { Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { ConsentGate } from '@/components/consent-gate';
import { RoleForm } from '@/components/role-form';
import { useDocuments } from '@/hooks/use-documents';
import { useI18n } from '@/i18n/provider';

function NewAnalysis() {
  const { t } = useI18n();
  const { documents } = useDocuments();
  const search = useSearchParams();
  const title = search.get('role');
  const code = search.get('code');

  return (
    <div className="mx-auto flex max-w-xl flex-col gap-5">
      <h1 className="text-3xl font-semibold tracking-tight">{t('role.title')}</h1>
      <ConsentGate>
        <div className="rounded-lg border bg-card p-5">
          <RoleForm
            documents={documents}
            initialRole={title ? { title, occupationCode: code ?? undefined } : null}
          />
        </div>
      </ConsentGate>
    </div>
  );
}

export default function NewAnalysisPage() {
  return (
    <Suspense>
      <NewAnalysis />
    </Suspense>
  );
}
