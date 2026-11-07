'use client';

import { Suspense, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { Check, Loader2 } from 'lucide-react';
import type { Analysis } from '@careerfit/shared';
import { ActionPlan } from '@/components/results/action-plan';
import { AllSkills } from '@/components/results/all-skills';
import { OtherRoles } from '@/components/results/other-roles';
import { Overview } from '@/components/results/overview';
import { ResultExtras } from '@/components/results/result-extras';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useI18n } from '@/i18n/provider';
import type { TextKey } from '@/i18n/translate';
import { getApi } from '@/lib/api';

const POLL_INTERVAL_MS = 2000;
const STAGES: { key: NonNullable<Analysis['stage']>; label: TextKey }[] = [
  { key: 'matching', label: 'progress.matching' },
  { key: 'planning', label: 'progress.planning' },
  { key: 'alternatives', label: 'progress.alternatives' },
];

function LiveProgress({ analysis }: { analysis: Analysis }) {
  const { t } = useI18n();
  const position = STAGES.findIndex((stage) => stage.key === analysis.stage);
  const currentLabel = position >= 0 ? t(STAGES[position].label) : t('progress.waiting');
  return (
    <section aria-labelledby="progress" className="flex flex-col gap-3 rounded-lg border bg-card p-5" data-testid="live-progress">
      <h2 id="progress" className="text-xl font-semibold">
        {t('progress.title')}
      </h2>
      <p className="text-sm text-muted-foreground">{t('progress.time')}</p>
      <p role="status" className="sr-only">
        {currentLabel}
      </p>
      <ol className="flex flex-col gap-2">
        {STAGES.map((stage, index) => {
          const done = position > index;
          const current = position === index;
          return (
            <li
              key={stage.key}
              aria-current={current ? 'step' : undefined}
              className={done || current ? 'flex items-center gap-2' : 'flex items-center gap-2 text-muted-foreground'}
            >
              {done ? (
                <Check aria-hidden="true" className="size-4 text-shown" />
              ) : current ? (
                <Loader2 aria-hidden="true" className="size-4 animate-spin" />
              ) : (
                <span aria-hidden="true" className="size-4 rounded-full border" />
              )}
              {t(stage.label)}
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function LoadingResult() {
  const { t } = useI18n();
  return (
    <div role="status" aria-label={t('common.loading')} className="flex flex-col gap-4">
      <Skeleton className="h-9 w-2/3" />
      <Skeleton className="h-64 w-full" />
    </div>
  );
}

function AnalysisView() {
  const { t, path, date, maybe } = useI18n();
  const { id } = useParams<{ id: string }>();
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [failedToLoad, setFailedToLoad] = useState(false);
  const [tab, setTab] = useState('overview');
  const loadedOnce = useRef(false);

  const working = !analysis || analysis.status === 'pending' || analysis.status === 'processing';

  useEffect(() => {
    if (!working || failedToLoad) return;
    let active = true;
    const load = () =>
      getApi()
        .analyses.get(id)
        .then((row) => {
          loadedOnce.current = true;
          if (active) setAnalysis(row);
        })
        .catch(() => {
          // A dropped request mid-way shouldn't end the wait, so it just tries again.
          if (active && !loadedOnce.current) setFailedToLoad(true);
        });
    void load();
    const timer = setInterval(() => void load(), POLL_INTERVAL_MS);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [id, working, failedToLoad]);

  if (failedToLoad) {
    return (
      <div className="flex flex-col items-start gap-3">
        <h1 className="text-2xl font-semibold">{t('results.loadFailedTitle')}</h1>
        <Alert variant="destructive">
          <AlertDescription>{t('results.loadFailed')}</AlertDescription>
        </Alert>
        <Button asChild variant="outline">
          <Link href={path('/analyses')}>{t('results.backToHistory')}</Link>
        </Button>
      </div>
    );
  }

  if (!analysis) return <LoadingResult />;

  if (analysis.status === 'failed') {
    return (
      <div className="flex flex-col items-start gap-3">
        <h1 className="text-2xl font-semibold">{t('results.failedTitle')}</h1>
        <Alert variant="destructive">
          <AlertDescription>
            {maybe(`errors.analysis.${analysis.errorCode}`) ?? t('errors.analysis.analysis_error')}
          </AlertDescription>
        </Alert>
        <Button asChild>
          <Link href={path('/analyses/new')}>{t('common.tryAgain')}</Link>
        </Button>
      </div>
    );
  }

  const result = analysis.result;
  const report = result?.report;

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-1">
        <h1 className="text-3xl font-semibold tracking-tight first-letter:uppercase">
          {result?.occupationName ?? analysis.role}
        </h1>
        <p className="text-muted-foreground">
          {[
            result?.region ? (maybe(`regions.${result.region}`) ?? result.region) : analysis.region,
            date(analysis.createdAt),
          ]
            .filter(Boolean)
            .join(' · ')}
        </p>
      </div>

      {working && <LiveProgress analysis={analysis} />}

      {result && (
        <Tabs value={tab} onValueChange={setTab} className="flex flex-col gap-4">
          <TabsList className="h-auto w-full flex-wrap justify-start sm:w-fit">
            <TabsTrigger value="overview">{t('results.tabOverview')}</TabsTrigger>
            <TabsTrigger value="plan" disabled={!report}>
              {t('results.tabPlan')}
            </TabsTrigger>
            <TabsTrigger value="roles" disabled={!report}>
              {t('results.tabRoles')}
            </TabsTrigger>
            <TabsTrigger value="skills">{t('results.tabSkills')}</TabsTrigger>
          </TabsList>
          <TabsContent value="overview">
            <Overview result={result} onOpenPlan={() => setTab('plan')} />
          </TabsContent>
          <TabsContent value="plan">{report && <ActionPlan report={report} />}</TabsContent>
          <TabsContent value="roles">
            {report && <OtherRoles roles={report.alternativeRoles} />}
          </TabsContent>
          <TabsContent value="skills">
            <AllSkills result={result} />
          </TabsContent>
        </Tabs>
      )}

      {analysis.status === 'completed' && result && !report && (
        <Alert>
          <AlertDescription>{t('results.reportFailed')}</AlertDescription>
        </Alert>
      )}

      {analysis.status === 'completed' && result && <ResultExtras analysisId={analysis.id} />}

      {result && (
        <footer className="flex flex-col gap-1 border-t pt-3 text-sm text-muted-foreground" data-testid="disclaimer">
          <p>{result.disclaimer}</p>
          <p>
            {result.marketLatestPosting
              ? t('results.scoredOnWithAds', {
                  date: date(result.asOf),
                  ads: date(result.marketLatestPosting),
                })
              : t('results.scoredOn', { date: date(result.asOf) })}
          </p>
        </footer>
      )}
    </div>
  );
}

export default function AnalysisPage() {
  return (
    <Suspense fallback={<LoadingResult />}>
      <AnalysisView />
    </Suspense>
  );
}
