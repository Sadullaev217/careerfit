import Link from 'next/link';
import { notFound } from 'next/navigation';
import { LanguageSwitcher } from '@/components/language-switcher';
import { ScoreReceipt } from '@/components/score-receipt';
import { Button } from '@/components/ui/button';
import { isLocale } from '@/i18n/config';
import { getDictionary } from '@/i18n/get-dictionary';
import { createTranslator } from '@/i18n/translate';

export default async function LandingPage({ params }: PageProps<'/[lang]'>) {
  const { lang } = await params;
  if (!isLocale(lang)) notFound();
  const { t, path } = createTranslator(lang, await getDictionary(lang));

  const sample = [
    { label: t('landing.sample.required'), points: 30, maxPoints: 40 },
    { label: t('landing.sample.other'), points: 6, maxPoints: 10 },
    { label: t('landing.sample.experience'), points: 20, maxPoints: 20 },
    { label: t('landing.sample.education'), points: 10, maxPoints: 15 },
    { label: t('landing.sample.portfolio'), points: 2, maxPoints: 5 },
    { label: t('landing.sample.seniority'), points: 8, maxPoints: 10 },
  ];
  const steps = [
    { title: t('landing.step1Title'), body: t('landing.step1Body') },
    { title: t('landing.step2Title'), body: t('landing.step2Body') },
    { title: t('landing.step3Title'), body: t('landing.step3Body') },
  ];
  const promises = [
    { title: t('landing.honest1Title'), body: t('landing.honest1Body') },
    { title: t('landing.honest2Title'), body: t('landing.honest2Body') },
    { title: t('landing.honest3Title'), body: t('landing.honest3Body') },
  ];

  return (
    <div className="flex grow flex-col">
      <header className="mx-auto flex w-full max-w-5xl items-center gap-2 px-4 py-3 sm:px-6">
        <span className="text-lg font-semibold tracking-tight">CareerFit</span>
        <div className="ms-auto flex items-center gap-1">
          <LanguageSwitcher />
          <Button asChild variant="ghost">
            <Link href={path('/login')}>{t('landing.logIn')}</Link>
          </Button>
        </div>
      </header>

      <main className="grow">
        <section className="mx-auto grid w-full max-w-5xl gap-8 px-4 py-8 sm:px-6 md:grid-cols-[1.1fr_1fr] md:items-center md:py-14">
          <div className="flex flex-col items-start gap-5">
            <h1 className="text-4xl leading-tight font-semibold tracking-tight sm:text-5xl">
              {t('landing.headline')}
            </h1>
            <p className="max-w-prose text-lg text-muted-foreground">{t('landing.subhead')}</p>
            <div className="flex flex-wrap items-center gap-3">
              <Button asChild size="lg">
                <Link href={path('/login?mode=signup')}>{t('landing.cta')}</Link>
              </Button>
              <span className="text-sm text-muted-foreground">{t('landing.ctaNote')}</span>
            </div>
          </div>
          <figure className="rounded-lg border bg-card p-5 shadow-sm">
            <figcaption className="mb-3 flex items-baseline justify-between gap-3 text-sm">
              <span className="font-medium">{t('landing.sampleTitle')}</span>
              <span className="text-muted-foreground">{t('landing.sampleLabel')}</span>
            </figcaption>
            <ScoreReceipt
              lines={sample}
              total={sample.reduce((sum, line) => sum + line.points, 0)}
              totalLabel={t('landing.sample.total')}
              ofLabel={(points, maxPoints) => t('common.pointsOf', { points, maxPoints })}
            />
          </figure>
        </section>

        <section aria-labelledby="how" className="border-y bg-card">
          <div className="mx-auto w-full max-w-5xl px-4 py-10 sm:px-6">
            <h2 id="how" className="text-2xl font-semibold">
              {t('landing.howTitle')}
            </h2>
            <ol className="mt-6 grid gap-6 md:grid-cols-3">
              {steps.map((step, index) => (
                <li key={step.title} className="flex gap-3">
                  <span className="font-mono text-lg font-medium text-primary tabular-nums">{index + 1}</span>
                  <div>
                    <h3 className="font-medium">{step.title}</h3>
                    <p className="mt-1 text-muted-foreground">{step.body}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section aria-labelledby="honest" className="mx-auto w-full max-w-5xl px-4 py-10 sm:px-6">
          <h2 id="honest" className="text-2xl font-semibold">
            {t('landing.honestTitle')}
          </h2>
          <ul className="mt-6 grid gap-6 md:grid-cols-3">
            {promises.map((promise) => (
              <li key={promise.title}>
                <h3 className="font-medium">{promise.title}</h3>
                <p className="mt-1 text-muted-foreground">{promise.body}</p>
              </li>
            ))}
          </ul>
        </section>
      </main>

      <footer className="border-t">
        <p className="mx-auto w-full max-w-5xl px-4 py-5 text-sm text-muted-foreground sm:px-6">
          {t('landing.footer')}
        </p>
      </footer>
    </div>
  );
}
