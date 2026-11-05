'use client';

import { CheckCircle2, Info } from 'lucide-react';
import type { ScoreResult } from '@careerfit/shared';
import { ScoreReceipt } from '@/components/score-receipt';
import { ScoreGauge } from '@/components/results/score-gauge';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useI18n } from '@/i18n/provider';

const MAX_STRENGTHS = 6;
const MAX_TOP_GAPS = 3;
const STRONG_SCORE = 65;
const MIDDLE_SCORE = 40;

export function Overview({
  result,
  onOpenPlan,
}: {
  result: ScoreResult;
  onOpenPlan: () => void;
}) {
  const { t, plural, money } = useI18n();
  const verdict =
    result.score >= STRONG_SCORE
      ? t('results.verdictStrong')
      : result.score >= MIDDLE_SCORE
        ? t('results.verdictMiddle')
        : t('results.verdictLow');
  const strengths = result.requiredSkills.filter((skill) => skill.level === 'yes').slice(0, MAX_STRENGTHS);
  const topGaps = result.report?.gaps.slice(0, MAX_TOP_GAPS) ?? [];
  const confidenceLabel = {
    high: t('results.confidenceHigh'),
    medium: t('results.confidenceMedium'),
    low: t('results.confidenceLow'),
  }[result.confidence.level];

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
      <div className="flex flex-col gap-6">
        <section aria-labelledby="your-match" className="flex flex-col gap-3 rounded-lg border bg-card p-5">
          <h2 id="your-match" className="sr-only">
            {t('results.yourMatch')}
          </h2>
          <ScoreGauge
            score={result.score}
            label={t('results.scoreLabel', { score: result.score })}
            outOfLabel={t('results.outOf')}
          />
          <p className="text-center font-medium">{verdict}</p>
          <p className="text-center text-sm text-muted-foreground">{t('results.notProbability')}</p>
          <div className="flex flex-col gap-1.5 border-t pt-3">
            <Badge variant="secondary" className="self-start">
              {confidenceLabel}
            </Badge>
            <ul className="flex flex-col gap-1 text-sm text-muted-foreground">
              {result.confidence.reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          </div>
        </section>

        <section aria-labelledby="pay" className="flex flex-col gap-2 rounded-lg border bg-card p-5">
          <h2 id="pay" className="font-medium">
            {t('results.payTitle')}
          </h2>
          {result.salary ? (
            <>
              <p className="font-mono text-2xl font-medium tabular-nums" data-testid="salary">
                {money(result.salary.low, result.salary.currency)} –{' '}
                {money(result.salary.high, result.salary.currency)}
              </p>
              <p className="text-sm text-muted-foreground">
                {t('results.payMedian', { amount: money(result.salary.marketMedian, result.salary.currency) })}
              </p>
              <p className="text-sm text-muted-foreground">{result.salary.basis}</p>
              {result.salary.concentrated && (
                <p className="flex gap-1.5 text-sm">
                  <Info aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
                  {t('results.payConcentrated')}
                </p>
              )}
            </>
          ) : (
            <p className="text-sm text-muted-foreground">{t('results.payNone')}</p>
          )}
        </section>
      </div>

      <div className="flex flex-col gap-6">
        <section aria-labelledby="strengths" className="flex flex-col gap-2 rounded-lg border bg-card p-5">
          <h2 id="strengths" className="font-medium">
            {t('results.strengthsTitle')}
          </h2>
          {strengths.length > 0 ? (
            <ul className="flex flex-col gap-1.5 text-sm" data-testid="strengths">
              {strengths.map((skill) => (
                <li key={skill.name} className="flex gap-1.5">
                  <CheckCircle2 aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-shown" />
                  <span className="first-letter:uppercase">{skill.name}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">{t('results.strengthsNone')}</p>
          )}
        </section>

        {topGaps.length > 0 && (
          <section aria-labelledby="top-gaps" className="flex flex-col gap-2 rounded-lg border bg-card p-5">
            <h2 id="top-gaps" className="font-medium">
              {t('results.topGapsTitle')}
            </h2>
            <ol className="flex flex-col gap-1.5 text-sm" data-testid="top-gaps">
              {topGaps.map((gap) => (
                <li key={gap.title} className="flex items-baseline justify-between gap-3">
                  <span className="first-letter:uppercase">{gap.title}</span>
                  <span className="whitespace-nowrap font-mono tabular-nums">
                    +{plural('results.points', gap.pointsAvailable)}
                  </span>
                </li>
              ))}
            </ol>
            <Button variant="link" className="h-auto self-start p-0" onClick={onOpenPlan}>
              {t('results.seePlan')}
            </Button>
          </section>
        )}

        <section aria-labelledby="how-calculated" className="flex flex-col gap-2 rounded-lg border bg-card p-5">
          <h2 id="how-calculated" className="font-medium">
            {t('results.howTitle')}
          </h2>
          <ScoreReceipt
            lines={result.categories.map((category) => ({
              label: category.label,
              points: category.points,
              maxPoints: category.maxPoints,
              reason: category.reason,
            }))}
            total={result.score}
            totalLabel={t('results.total')}
            ofLabel={(points, maxPoints) => t('common.pointsOf', { points, maxPoints })}
          />
          {result.notScored.length > 0 && (
            <div className="mt-2 border-t pt-3 text-sm text-muted-foreground">
              <p className="font-medium">{t('results.leftOut')}</p>
              <ul className="mt-1 flex flex-col gap-1">
                {result.notScored.map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            </div>
          )}
          <p className="text-xs text-muted-foreground">
            {t('results.weightsUsed', { field: result.weightsUsed })}
          </p>
        </section>
      </div>
    </div>
  );
}
