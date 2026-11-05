'use client';

import { useRef, useState } from 'react';
import { FileUp } from 'lucide-react';
import { MAX_UPLOAD_BYTES } from '@careerfit/shared';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Progress } from '@/components/ui/progress';
import { useI18n } from '@/i18n/provider';
import { getApi } from '@/lib/api';
import { apiErrorText } from '@/lib/api-error';
import { cn } from '@/lib/utils';

const ACCEPTED =
  '.pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document';

export function ResumeUploader({
  type = 'resume',
  onUploaded,
}: {
  type?: 'resume' | 'cover_letter';
  onUploaded: () => void | Promise<void>;
}) {
  const i18n = useI18n();
  const { t } = i18n;
  const input = useRef<HTMLInputElement>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const uploading = progress !== null;

  async function send(file: File | undefined) {
    if (!file || uploading) return;
    setError(null);
    if (file.size > MAX_UPLOAD_BYTES) {
      setError(t('errors.api.too_large'));
    } else {
      const form = new FormData();
      form.append('type', type);
      form.append('file', file);
      setProgress(0);
      try {
        await getApi().documents.upload(form, setProgress);
        await onUploaded();
      } catch (err) {
        setError(apiErrorText(i18n, err, 'documents.uploadFailed'));
      }
      setProgress(null);
    }
    if (input.current) input.current.value = '';
  }

  return (
    <div className="flex flex-col gap-3">
      <label
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          void send(event.dataTransfer.files[0]);
        }}
        className={cn(
          'flex cursor-pointer flex-col items-center gap-2 rounded-lg border-2 border-dashed border-input bg-card px-4 py-8 text-center transition-colors hover:bg-muted focus-within:ring-3 focus-within:ring-ring/50',
          dragging && 'bg-accent',
          uploading && 'pointer-events-none opacity-60',
        )}
      >
        <FileUp aria-hidden="true" className="size-6 text-primary" />
        <span className="font-medium">
          {type === 'resume' ? t('documents.chooseResume') : t('documents.chooseCoverLetter')}
        </span>
        <span className="text-sm text-muted-foreground">{t('documents.fileHint')}</span>
        <input
          ref={input}
          type="file"
          accept={ACCEPTED}
          disabled={uploading}
          className="sr-only"
          onChange={(event) => void send(event.target.files?.[0])}
        />
      </label>
      {uploading && (
        <div role="status" className="flex flex-col gap-1.5 text-sm">
          <span>
            {progress < 1
              ? t('documents.uploading', { percent: Math.round(progress * 100) })
              : t('documents.uploaded')}
          </span>
          <Progress value={Math.round(progress * 100)} aria-label={t('documents.uploadProgress')} />
        </div>
      )}
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
    </div>
  );
}
