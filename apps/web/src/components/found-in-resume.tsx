'use client';

import { useEffect, useState } from 'react';
import type { DocumentAnalysis } from '@careerfit/shared';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';
import { useI18n } from '@/i18n/provider';
import { getApi } from '@/lib/api';
import { apiErrorText } from '@/lib/api-error';

function Section({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div className="flex flex-col gap-1">
      <h4 className="font-medium">{title}</h4>
      <ul className="list-disc ps-5">
        {items.map((item, index) => (
          <li key={`${item}-${index}`}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

export function FoundInResume({ documentId }: { documentId: string }) {
  const i18n = useI18n();
  const { t, maybe } = i18n;
  const [analysis, setAnalysis] = useState<DocumentAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getApi()
      .documents.analysis(documentId)
      .then(setAnalysis)
      .catch((err: unknown) => setError(apiErrorText(i18n, err, 'found.loadFailed')));
  }, [documentId, i18n]);

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }
  if (!analysis) {
    return <Skeleton aria-label={t('common.loading')} role="status" className="h-24 w-full" />;
  }

  const { profile, matchedSkills } = analysis;
  const dates = (start: string | null, end: string | null, current: boolean) => {
    const finish = current ? t('found.present') : end;
    if (!start && !finish) return t('found.noDates');
    return `${start ?? '?'} – ${finish ?? '?'}`;
  };

  return (
    <div data-testid="analysis" className="flex flex-col gap-3 text-sm">
      <p className="text-muted-foreground">{t('found.note')}</p>
      <p>
        <span className="font-medium">{t('found.level')}:</span>{' '}
        {maybe(`seniority.${profile.seniority}`) ?? profile.seniority}
        {profile.industry_en && (
          <>
            {' · '}
            <span className="font-medium">{t('found.industry')}:</span> {profile.industry_en}
          </>
        )}
      </p>
      <Section
        title={t('found.skills', { found: profile.skills.length, matched: matchedSkills.length })}
        items={profile.skills.map((skill) => skill.name)}
      />
      <Section
        title={t('found.workHistory')}
        items={profile.work_history.map(
          (job) =>
            `${job.title_en}${job.employer ? `, ${job.employer}` : ''} (${dates(job.start_date, job.end_date, job.is_current)})`,
        )}
      />
      <Section
        title={t('found.education')}
        items={profile.education.map((item) =>
          [item.degree, item.field_of_study, item.institution, item.end_year].filter(Boolean).join(', '),
        )}
      />
      <Section
        title={t('found.certifications')}
        items={profile.certifications.map((item) =>
          [item.name, item.issuer, item.year].filter(Boolean).join(', '),
        )}
      />
      <Section
        title={t('found.languages')}
        items={profile.languages.map((item) =>
          item.level ? `${item.name_en} (${item.level})` : item.name_en,
        )}
      />
      <Section title={t('found.projects')} items={profile.projects.map((item) => item.name)} />
      <Section
        title={t('found.missing')}
        items={profile.flags.map((flag) => maybe(`found.flags.${flag.field}`) ?? flag.field)}
      />
    </div>
  );
}
