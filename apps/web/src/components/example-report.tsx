'use client';

import { useState } from 'react';
import Link from 'next/link';
import { LanguageSwitcher } from '@/components/language-switcher';
import { ActionPlan } from '@/components/results/action-plan';
import { AllSkills } from '@/components/results/all-skills';
import { OtherRoles } from '@/components/results/other-roles';
import { Overview } from '@/components/results/overview';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import type { ExampleAnalysis } from '@/content/example-analysis';
import { useI18n } from '@/i18n/provider';

/**
 * A saved result that anyone can read, signed in or not. It uses the result page's own sections and
 * leaves out what needs an account: tailoring, the PDF and starting another analysis.
 */
export function ExampleReport({ analysis }: { analysis: ExampleAnalysis }) {
  const { t, path, date, maybe } = useI18n();
  const [tab, setTab] = useState('overview');
  const { result } = analysis;
  const scoredOn = date(analysis.completedAt ?? analysis.createdAt);

  return (
    <div className="flex min-h-full grow flex-col">
      <header className="border-b bg-card">
        <div className="mx-auto flex w-full max-w-5xl items-center gap-2 px-4 py-2 sm:px-6">
          <Link href={path('/')} className="me-auto text-lg font-semibold tracking-tight">
            CareerFit
          </Link>
          <LanguageSwitcher />
          <Button asChild variant="ghost">
            <Link href={path('/login')}>{t('landing.logIn')}</Link>
          </Button>
        </div>
      </header>

      <main
        id="main"
        className="mx-auto flex w-full max-w-5xl grow flex-col gap-5 px-4 py-6 sm:px-6 sm:py-8"
      >
        <div
          role="note"
          className="flex flex-col items-start gap-3 rounded-lg border border-dashed p-4 sm:flex-row sm:items-center sm:justify-between"
          data-testid="example-note"
        >
          <p className="text-sm">{t('example.note')}</p>
          <Button asChild className="shrink-0">
            <Link href={path('/login?mode=signup')}>{t('landing.cta')}</Link>
          </Button>
        </div>

        <div className="flex flex-col gap-1">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <h1 className="text-3xl font-semibold tracking-tight first-letter:uppercase">
              {result.occupationName}
            </h1>
            <Badge variant="secondary">{t('landing.sampleLabel')}</Badge>
          </div>
          <p className="text-muted-foreground">
            {[maybe(`regions.${result.region}`) ?? result.region, date(analysis.createdAt)].join(
              ' · ',
            )}
          </p>
        </div>

        <Tabs value={tab} onValueChange={setTab} className="flex flex-col gap-4">
          <TabsList className="h-auto w-full flex-wrap justify-start sm:w-fit">
            <TabsTrigger value="overview">{t('results.tabOverview')}</TabsTrigger>
            <TabsTrigger value="plan">{t('results.tabPlan')}</TabsTrigger>
            <TabsTrigger value="roles">{t('results.tabRoles')}</TabsTrigger>
            <TabsTrigger value="skills">{t('results.tabSkills')}</TabsTrigger>
          </TabsList>
          <TabsContent value="overview">
            <Overview result={result} onOpenPlan={() => setTab('plan')} />
          </TabsContent>
          <TabsContent value="plan">
            <ActionPlan report={result.report} />
          </TabsContent>
          <TabsContent value="roles">
            <OtherRoles roles={result.report.alternativeRoles} showRunButton={false} />
          </TabsContent>
          <TabsContent value="skills">
            <AllSkills result={result} />
          </TabsContent>
        </Tabs>

        <section
          aria-labelledby="example-signup"
          className="flex flex-col items-start gap-3 rounded-lg border bg-card p-5"
          data-testid="example-signup"
        >
          <h2 id="example-signup" className="text-xl font-semibold">
            {t('example.signupTitle')}
          </h2>
          <p className="text-sm text-muted-foreground">{t('example.signupBody')}</p>
          <Button asChild>
            <Link href={path('/login?mode=signup')}>{t('landing.cta')}</Link>
          </Button>
        </section>

        <footer
          className="flex flex-col gap-1 border-t pt-3 text-sm text-muted-foreground"
          data-testid="disclaimer"
        >
          <p>{result.disclaimer}</p>
          <p>
            {result.marketLatestPosting
              ? t('results.scoredOnWithAds', {
                  date: scoredOn,
                  ads: date(result.marketLatestPosting),
                })
              : t('results.scoredOn', { date: scoredOn })}
          </p>
        </footer>
      </main>

      <footer className="border-t">
        <nav
          aria-label={t('legal.nav')}
          className="mx-auto flex w-full max-w-5xl flex-wrap gap-x-5 gap-y-1 px-4 py-5 text-sm sm:px-6"
        >
          <Link href={path('/privacy')} className="underline underline-offset-4">
            {t('legal.privacy')}
          </Link>
          <Link href={path('/terms')} className="underline underline-offset-4">
            {t('legal.terms')}
          </Link>
          <Link href={path('/how-scoring-works')} className="underline underline-offset-4">
            {t('legal.howScoreWorks')}
          </Link>
        </nav>
      </footer>
    </div>
  );
}
