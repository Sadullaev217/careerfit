'use client';

import { useState } from 'react';
import { Check } from 'lucide-react';
import { ConsentGate } from '@/components/consent-gate';
import { DocumentList } from '@/components/document-list';
import { PortfolioForm } from '@/components/portfolio-form';
import { ResumeUploader } from '@/components/resume-uploader';
import { RoleForm } from '@/components/role-form';
import { Button } from '@/components/ui/button';
import { useDocuments } from '@/hooks/use-documents';
import { useI18n } from '@/i18n/provider';
import { cn } from '@/lib/utils';

export default function OnboardingPage() {
  const { t } = useI18n();
  const { documents, failed, refresh } = useDocuments();
  const [chosenStep, setChosenStep] = useState<number | null>(null);
  const hasResume = documents?.some((document) => document.type === 'resume') ?? false;
  const step = chosenStep ?? (hasResume ? 2 : 1);

  const steps = [t('onboarding.step1'), t('onboarding.step2'), t('onboarding.step3')];

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold tracking-tight">{t('onboarding.title')}</h1>
        <p className="text-muted-foreground">{t('onboarding.intro')}</p>
      </div>

      <ol
        className="flex flex-col gap-2 sm:flex-row sm:gap-6"
        aria-label={t('onboarding.progress')}
      >
        {steps.map((label, index) => {
          const number = index + 1;
          const done = number < step;
          const current = number === step;
          return (
            <li
              key={label}
              aria-current={current ? 'step' : undefined}
              className={cn(
                'flex items-center gap-2 text-sm',
                current ? 'font-medium' : 'text-muted-foreground',
              )}
            >
              <span
                className={cn(
                  'flex size-6 shrink-0 items-center justify-center rounded-full border font-mono text-xs',
                  (done || current) && 'border-primary bg-primary text-primary-foreground',
                )}
              >
                {done ? <Check aria-hidden="true" className="size-3.5" /> : number}
              </span>
              {label}
            </li>
          );
        })}
      </ol>

      <ConsentGate>
        <section className="flex flex-col gap-4 rounded-lg border bg-card p-5">
          {step === 1 && (
            <>
              <h2 className="text-xl font-semibold">{t('onboarding.resumeTitle')}</h2>
              <p className="text-sm text-muted-foreground">{t('onboarding.resumePrivacy')}</p>
              <ResumeUploader
                onUploaded={async () => {
                  await refresh();
                  setChosenStep(2);
                }}
              />
            </>
          )}
          {step === 2 && (
            <>
              <h2 className="text-xl font-semibold">{t('onboarding.portfolioTitle')}</h2>
              <p className="text-sm text-muted-foreground">{t('onboarding.portfolioBody')}</p>
              <PortfolioForm onAdded={refresh} />
              <DocumentList documents={documents} failed={failed} onChanged={refresh} />
              <Button size="lg" className="self-start" onClick={() => setChosenStep(3)}>
                {t('common.continue')}
              </Button>
            </>
          )}
          {step === 3 && (
            <>
              <h2 className="text-xl font-semibold">{t('onboarding.roleTitle')}</h2>
              <RoleForm documents={documents} />
              <Button variant="link" className="self-start p-0" onClick={() => setChosenStep(2)}>
                {t('common.back')}
              </Button>
            </>
          )}
        </section>
      </ConsentGate>
    </div>
  );
}
