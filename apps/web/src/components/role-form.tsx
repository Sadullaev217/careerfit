'use client';

import { useMemo, useState, type FormEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import type { Document } from '@careerfit/shared';
import { RegionSelect } from '@/components/region-select';
import { RoleCombobox, type ChosenRole } from '@/components/role-combobox';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { useI18n } from '@/i18n/provider';
import { getApi } from '@/lib/api';
import { apiErrorText } from '@/lib/api-error';
import { DEFAULT_REGION } from '@/lib/regions';

export function RoleForm({
  documents,
  initialRole = null,
}: {
  documents: Document[] | null;
  initialRole?: ChosenRole | null;
}) {
  const i18n = useI18n();
  const { t, path, locale } = i18n;
  const router = useRouter();
  const [picked, setPicked] = useState<string | null>(null);
  const [role, setRole] = useState<ChosenRole | null>(initialRole);
  const [region, setRegion] = useState<string>(DEFAULT_REGION);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const resumes = useMemo(
    () => (documents ?? []).filter((document) => document.type === 'resume'),
    [documents],
  );
  const ready = resumes.filter((resume) => resume.extractionStatus === 'ready');
  const stillReading = resumes.some(
    (resume) =>
      resume.status === 'pending' ||
      resume.status === 'parsing' ||
      resume.extractionStatus === 'pending' ||
      resume.extractionStatus === 'running',
  );
  const documentId = picked ?? ready[0]?.id ?? null;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!documentId) return;
    if (!role) {
      setError(t('role.pickFirst'));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const { analysisId } = await getApi().analyses.start({
        documentId,
        role: role.title,
        occupationCode: role.occupationCode,
        region,
        language: locale,
      });
      router.push(path(`/analyses/${analysisId}`));
    } catch (err) {
      setError(apiErrorText(i18n, err, 'role.startFailed'));
      setBusy(false);
    }
  }

  if (documents === null) {
    return (
      <div role="status" aria-label={t('common.loading')} className="flex flex-col gap-3">
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-16 w-full" />
      </div>
    );
  }

  if (ready.length === 0 && !stillReading) {
    return (
      <div className="flex flex-col items-start gap-3">
        <p>{t('role.needResume')}</p>
        <Button asChild>
          <Link href={path('/onboarding')}>{t('role.uploadResume')}</Link>
        </Button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      {ready.length > 1 && (
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="resume">{t('role.resume')}</Label>
          <Select value={documentId ?? undefined} onValueChange={setPicked}>
            <SelectTrigger id="resume" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {ready.map((resume) => (
                <SelectItem key={resume.id} value={resume.id}>
                  {resume.fileName ?? resume.id}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="role">{t('role.job')}</Label>
        <RoleCombobox id="role" value={role} onChange={setRole} />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="region">{t('role.where')}</Label>
        <RegionSelect id="region" value={region} onChange={setRegion} />
      </div>
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {ready.length === 0 && stillReading && (
        <p role="status" className="text-sm text-muted-foreground">
          {t('role.stillReading')}
        </p>
      )}
      <Button type="submit" size="lg" disabled={busy || !documentId} className="self-start">
        {busy ? t('role.starting') : t('role.start')}
      </Button>
    </form>
  );
}
