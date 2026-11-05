'use client';

import { AlertTriangle } from 'lucide-react';
import type { Report } from '@careerfit/shared';
import { Badge } from '@/components/ui/badge';
import { useI18n } from '@/i18n/provider';
import type { TextKey } from '@/i18n/translate';

const PRIORITY: Record<Report['actions'][number]['priority'], TextKey> = {
  high: 'plan.priorityHigh',
  medium: 'plan.priorityMedium',
  low: 'plan.priorityLow',
};
const KIND: Record<Report['actions'][number]['kind'], TextKey> = {
  course: 'plan.kindCourse',
  certification: 'plan.kindCertification',
  project: 'plan.kindProject',
  experience: 'plan.kindExperience',
};

function Stage({ title, steps }: { title: string; steps: string[] }) {
  if (steps.length === 0) return null;
  return (
    <div className="flex flex-col gap-1.5">
      <h3 className="font-medium">{title}</h3>
      <ul className="flex list-disc flex-col gap-1 ps-5 text-sm">
        {steps.map((step) => (
          <li key={step}>{step}</li>
        ))}
      </ul>
    </div>
  );
}

export function ActionPlan({ report }: { report: Report }) {
  const { t, plural, maybe } = useI18n();
  return (
    <div className="flex flex-col gap-6" data-testid="action-report">
      <section aria-labelledby="plan-stages" className="flex flex-col gap-4 rounded-lg border bg-card p-5" data-testid="plan">
        <h2 id="plan-stages" className="text-xl font-semibold">
          {t('plan.stagesTitle')}
        </h2>
        <div className="grid gap-4 md:grid-cols-3">
          <Stage title={t('plan.days30')} steps={report.plan.thirtyDays} />
          <Stage title={t('plan.days60')} steps={report.plan.sixtyDays} />
          <Stage title={t('plan.days90')} steps={report.plan.ninetyDays} />
        </div>
        <Stage title={t('plan.later')} steps={report.plan.later} />
      </section>

      {report.actions.length > 0 && (
        <section aria-labelledby="next-steps" className="flex flex-col gap-3">
          <h2 id="next-steps" className="text-xl font-semibold">
            {t('plan.nextStepsTitle')}
          </h2>
          <ul className="flex flex-col divide-y rounded-lg border bg-card">
            {report.actions.map((action) => (
              <li key={action.gap} data-testid="action" className="flex flex-col gap-1.5 p-5">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="secondary">{t(PRIORITY[action.priority])}</Badge>
                  <Badge variant="outline">{t(KIND[action.kind])}</Badge>
                  <span className="text-sm text-muted-foreground">
                    {t('plan.about', { duration: plural('plan.weeks', action.effortWeeks) })}
                  </span>
                </div>
                <h3 className="font-medium">{action.title}</h3>
                <p className="text-sm text-muted-foreground">
                  {t('plan.forGap', { gap: action.gap })}
                </p>
                <p className="text-sm">{action.details}</p>
                {action.expectedResult && (
                  <p className="text-sm">{t('plan.endUpWith', { result: action.expectedResult })}</p>
                )}
                {action.providers.length > 0 && (
                  <p className="text-sm">
                    {t('plan.placesToLook', {
                      places: action.providers
                        .map((provider) => maybe(`providers.${provider}`) ?? provider)
                        .join(', '),
                    })}
                  </p>
                )}
                {action.uncertain && (
                  <p className="flex gap-1.5 text-sm font-medium text-partly">
                    <AlertTriangle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
                    {t('plan.uncertain')}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {report.rewrites.length > 0 && (
        <section aria-labelledby="rewrites" className="flex flex-col gap-3">
          <h2 id="rewrites" className="text-xl font-semibold">
            {t('plan.rewritesTitle')}
          </h2>
          <p className="text-sm text-muted-foreground">{t('plan.rewritesNote')}</p>
          <ul className="flex flex-col divide-y rounded-lg border bg-card">
            {report.rewrites.map((rewrite) => (
              <li key={rewrite.before} data-testid="rewrite" className="grid gap-3 p-5 md:grid-cols-2">
                <div>
                  <p className="text-xs font-medium text-muted-foreground uppercase">{t('plan.before')}</p>
                  <p className="text-sm text-muted-foreground">{rewrite.before}</p>
                </div>
                <div>
                  <p className="text-xs font-medium text-primary uppercase">{t('plan.after')}</p>
                  <p className="text-sm">{rewrite.after}</p>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {report.gaps.length > 0 && (
        <section aria-labelledby="all-gaps" className="flex flex-col gap-3">
          <h2 id="all-gaps" className="text-xl font-semibold">
            {t('plan.gapsTitle')}
          </h2>
          <ol className="flex flex-col divide-y rounded-lg border bg-card">
            {report.gaps.map((gap) => (
              <li key={gap.title} data-testid="gap" className="flex items-start justify-between gap-4 p-4">
                <div className="min-w-0">
                  <p className="font-medium first-letter:uppercase">{gap.title}</p>
                  <p className="text-sm text-muted-foreground">{gap.detail}</p>
                </div>
                <span className="whitespace-nowrap font-mono text-sm tabular-nums">
                  +{plural('results.points', gap.pointsAvailable)}
                </span>
              </li>
            ))}
          </ol>
        </section>
      )}

      <ul className="flex list-disc flex-col gap-1 ps-5 text-sm text-muted-foreground" data-testid="notes">
        {report.notes.map((note) => (
          <li key={note}>{note}</li>
        ))}
      </ul>
    </div>
  );
}
