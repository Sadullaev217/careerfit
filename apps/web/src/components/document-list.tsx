'use client';

import { useState } from 'react';
import { DEMO_SITE } from '@/components/demo';
import { AlertCircle, CheckCircle2, Loader2, Trash2 } from 'lucide-react';
import type { Document } from '@careerfit/shared';
import { FoundInResume } from '@/components/found-in-resume';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useI18n } from '@/i18n/provider';
import type { TextKey, Translator } from '@/i18n/translate';
import { getApi } from '@/lib/api';
import { apiErrorText } from '@/lib/api-error';

const TYPE_LABELS: Record<Document['type'], TextKey> = {
  resume: 'documents.typeResume',
  cover_letter: 'documents.typeCoverLetter',
  portfolio_link: 'documents.typePortfolio',
};

type Status = { state: 'working' | 'done' | 'failed'; text: string };

function documentStatus(document: Document, i18n: Translator): Status {
  const { t, maybe } = i18n;
  if (document.status === 'failed') {
    const code = document.errorCode;
    return {
      state: 'failed',
      text: (code && maybe(`errors.document.${code}`)) || t('errors.document.parse_error'),
    };
  }
  if (document.status !== 'ready') return { state: 'working', text: t('documents.statusReading') };
  if (document.extractionStatus === 'failed') {
    const code = document.extractionErrorCode;
    return {
      state: 'failed',
      text: (code && maybe(`errors.extraction.${code}`)) || t('errors.extraction.extraction_error'),
    };
  }
  if (document.extractionStatus === 'pending' || document.extractionStatus === 'running') {
    return { state: 'working', text: t('documents.statusAnalysing') };
  }
  return { state: 'done', text: t('documents.statusReady') };
}

function StatusLine({ status }: { status: Status }) {
  const Icon =
    status.state === 'working' ? Loader2 : status.state === 'done' ? CheckCircle2 : AlertCircle;
  const colour =
    status.state === 'done' ? 'text-shown' : status.state === 'failed' ? 'text-missing' : '';
  return (
    <span role="status" className={`flex items-center gap-1.5 text-sm ${colour}`}>
      <Icon
        aria-hidden="true"
        className={status.state === 'working' ? 'size-4 shrink-0 animate-spin' : 'size-4 shrink-0'}
      />
      {status.text}
    </span>
  );
}

/** When the stored file goes, and a way to keep it. Links have no stored file. */
function Retention({ document, onKeep }: { document: Document; onKeep: (keep: boolean) => void }) {
  const { t, date } = useI18n();
  if (document.type === 'portfolio_link') return null;
  // In the public demo the whole account goes after 30 days, before any file's 90 days are up.
  if (DEMO_SITE) {
    return <span className="text-sm text-muted-foreground">{t('demo.retention')}</span>;
  }
  if (document.fileDeletedAt) {
    return (
      <span className="text-sm text-muted-foreground">
        {t('documents.fileDeleted', { date: date(document.fileDeletedAt) })}
      </span>
    );
  }
  return (
    <div className="flex flex-col gap-1 text-sm">
      <span className="text-muted-foreground">
        {document.keep || !document.deleteAfter
          ? t('documents.kept')
          : t('documents.deleteAfter', { date: date(document.deleteAfter) })}
      </span>
      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          className="size-4 accent-primary"
          checked={document.keep}
          onChange={(event) => onKeep(event.target.checked)}
        />
        {t('documents.keepLabel')}
      </label>
    </div>
  );
}

export function DocumentList({
  documents,
  failed,
  onChanged,
}: {
  documents: Document[] | null;
  failed: boolean;
  onChanged: () => void | Promise<void>;
}) {
  const i18n = useI18n();
  const { t } = i18n;
  const [error, setError] = useState<string | null>(null);

  async function setKeep(document: Document, keep: boolean) {
    setError(null);
    try {
      await getApi().documents.setKeep(document.id, keep);
      await onChanged();
    } catch (err) {
      setError(apiErrorText(i18n, err, 'documents.keepFailed'));
    }
  }

  async function remove(document: Document) {
    setError(null);
    try {
      await getApi().documents.delete(document.id);
      await onChanged();
    } catch (err) {
      setError(apiErrorText(i18n, err, 'documents.deleteFailed'));
    }
  }

  if (failed) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{t('documents.loadFailed')}</AlertDescription>
      </Alert>
    );
  }
  if (documents === null) {
    return (
      <div role="status" aria-label={t('common.loading')} className="flex flex-col gap-2">
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-20 w-full" />
      </div>
    );
  }
  if (documents.length === 0) {
    return <p className="text-muted-foreground">{t('documents.empty')}</p>;
  }

  return (
    <div className="flex flex-col gap-2">
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      <ul className="flex flex-col divide-y rounded-lg border bg-card">
        {documents.map((document) => {
          const label = document.fileName ?? document.url ?? '';
          return (
            <li key={document.id} data-testid="document-row" className="flex items-start gap-3 p-4">
              <div className="flex min-w-0 grow flex-col gap-1">
                <span className="font-medium break-words">{label}</span>
                <span className="text-sm text-muted-foreground">
                  {t(TYPE_LABELS[document.type])}
                </span>
                <StatusLine status={documentStatus(document, i18n)} />
                <Retention document={document} onKeep={(keep) => void setKeep(document, keep)} />
                {document.type === 'resume' && document.extractionStatus === 'ready' && (
                  <details className="mt-1">
                    <summary className="cursor-pointer text-sm font-medium text-primary underline underline-offset-4">
                      {t('documents.seeFound')}
                    </summary>
                    <div className="pt-3">
                      <FoundInResume documentId={document.id} />
                    </div>
                  </details>
                )}
              </div>
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={t('documents.deleteNamed', { name: label })}
                  >
                    <Trash2 aria-hidden="true" />
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>
                      {t('documents.deleteTitle', { name: label })}
                    </AlertDialogTitle>
                    <AlertDialogDescription>
                      {document.type === 'resume'
                        ? t('documents.deleteResumeBody')
                        : t('documents.deleteBody')}
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                    <AlertDialogAction onClick={() => void remove(document)}>
                      {t('common.delete')}
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
