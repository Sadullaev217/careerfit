'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ChevronRight, Loader2 } from 'lucide-react';
import type { Analysis } from '@careerfit/shared';
import { HistoryChart } from '@/components/history-chart';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
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
import { usePlan } from '@/hooks/use-plan';
import { useI18n } from '@/i18n/provider';
import { getApi } from '@/lib/api';

function roleName(analysis: Analysis): string {
  return analysis.result?.occupationName ?? analysis.role ?? '';
}

// By code, so the same job run in English and in Russian still forms one line on the chart.
function roleKey(analysis: Analysis): string {
  return analysis.result?.occupationCode ?? roleName(analysis);
}

export default function HistoryPage() {
  const { t, path, date, maybe } = useI18n();
  const router = useRouter();
  const [analyses, setAnalyses] = useState<Analysis[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [chosenRole, setChosenRole] = useState<string | null>(null);
  // Progress over time is part of Pro. Everyone keeps the full list of results below it.
  const { plan } = usePlan();

  useEffect(() => {
    const api = getApi();
    api.analyses
      .list()
      .then(async (rows) => {
        // Someone with nothing here yet belongs in the guided start.
        if (rows.length === 0 && (await api.documents.list()).length === 0) {
          router.replace(path('/onboarding'));
          return;
        }
        setAnalyses(rows);
      })
      .catch(() => setFailed(true));
  }, [path, router]);

  const scored = useMemo(
    () => (analyses ?? []).filter((row) => row.status === 'completed' && row.score !== null),
    [analyses],
  );
  const roles = useMemo(() => {
    const groups = new Map<string, { name: string; count: number }>();
    for (const row of scored) {
      const group = groups.get(roleKey(row));
      groups.set(roleKey(row), { name: roleName(row), count: (group?.count ?? 0) + 1 });
    }
    return [...groups.entries()].sort((a, b) => b[1].count - a[1].count);
  }, [scored]);
  const role = chosenRole ?? roles[0]?.[0] ?? null;
  const chartName = roles.find(([key]) => key === role)?.[1].name ?? '';
  const points = scored
    .filter((row) => roleKey(row) === role)
    .map((row) => ({ id: row.id, score: row.score as number, date: row.createdAt }))
    .reverse();

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-3xl font-semibold tracking-tight">{t('history.title')}</h1>
        <Button asChild>
          <Link href={path('/analyses/new')}>{t('nav.newAnalysis')}</Link>
        </Button>
      </div>

      {failed && (
        <Alert variant="destructive">
          <AlertDescription>{t('history.loadFailed')}</AlertDescription>
        </Alert>
      )}

      {!failed && analyses === null && (
        <div role="status" aria-label={t('common.loading')} className="flex flex-col gap-3">
          <Skeleton className="h-52 w-full" />
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
      )}

      {analyses?.length === 0 && (
        <div className="flex flex-col items-start gap-3 rounded-lg border bg-card p-6">
          <h2 className="text-xl font-semibold">{t('history.emptyTitle')}</h2>
          <p className="text-muted-foreground">{t('history.emptyBody')}</p>
          <Button asChild>
            <Link href={path('/analyses/new')}>{t('nav.newAnalysis')}</Link>
          </Button>
        </div>
      )}

      {role && plan && plan.plan !== 'pro' && (
        <section
          aria-labelledby="progress-title"
          className="flex flex-col items-start gap-3 rounded-lg border bg-card p-5"
          data-testid="progress-locked"
        >
          <h2 id="progress-title" className="text-xl font-semibold">
            {t('history.proTitle')}
          </h2>
          <p className="text-muted-foreground">{t('history.proBody')}</p>
          <Button asChild variant="outline">
            <Link href={path('/pricing')}>{t('billing.seePlans')}</Link>
          </Button>
        </section>
      )}

      {role && plan?.plan === 'pro' && (
        <section aria-labelledby="progress-title" className="flex flex-col gap-3 rounded-lg border bg-card p-5">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <h2 id="progress-title" className="text-xl font-semibold">
              {t('history.progressTitle')}
            </h2>
            {roles.length > 1 && (
              <div className="flex w-full flex-col gap-1.5 sm:w-72">
                <Label htmlFor="chart-role">{t('history.chooseRole')}</Label>
                <Select value={role} onValueChange={setChosenRole}>
                  <SelectTrigger id="chart-role" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {roles.map(([key, group]) => (
                      <SelectItem key={key} value={key}>
                        {group.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
          </div>
          <HistoryChart points={points} label={t('history.chartLabel', { role: chartName })} />
          {points.length < 2 && (
            <p className="text-sm text-muted-foreground">{t('history.onePoint')}</p>
          )}
        </section>
      )}

      {analyses && analyses.length > 0 && (
        <section aria-labelledby="all-runs" className="flex flex-col gap-3">
          <h2 id="all-runs" className="text-xl font-semibold">
            {t('history.allTitle')}
          </h2>
          <ul className="flex flex-col divide-y rounded-lg border bg-card">
            {analyses.map((row) => {
              const working = row.status === 'pending' || row.status === 'processing';
              return (
                <li key={row.id} data-testid="history-row">
                  <Link
                    href={path(`/analyses/${row.id}`)}
                    className="flex items-center gap-4 p-4 hover:bg-muted"
                  >
                    <span className="w-12 shrink-0 font-mono text-2xl font-medium tabular-nums">
                      {row.score !== null ? row.score : '–'}
                    </span>
                    <span className="flex min-w-0 grow flex-col">
                      <span className="font-medium first-letter:uppercase">{roleName(row)}</span>
                      <span className="text-sm text-muted-foreground">
                        {[row.region && (maybe(`regions.${row.region}`) ?? row.region), date(row.createdAt)]
                          .filter(Boolean)
                          .join(' · ')}
                      </span>
                    </span>
                    {working && (
                      <Badge variant="secondary" className="gap-1">
                        <Loader2 aria-hidden="true" className="size-3 animate-spin" />
                        {t('history.working')}
                      </Badge>
                    )}
                    {row.status === 'failed' && <Badge variant="destructive">{t('history.failed')}</Badge>}
                    <ChevronRight aria-hidden="true" className="size-4 shrink-0 text-muted-foreground" />
                  </Link>
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </div>
  );
}
