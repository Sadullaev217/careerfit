'use client';

import { useState, type FormEvent } from 'react';
import type { MarketRequirements } from '@careerfit/shared';
import { RegionSelect } from '@/components/region-select';
import { RoleCombobox, type ChosenRole } from '@/components/role-combobox';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { useI18n } from '@/i18n/provider';
import { getApi } from '@/lib/api';
import { apiErrorText } from '@/lib/api-error';
import { DEFAULT_REGION } from '@/lib/regions';

const MAX_BREAKDOWN_ROWS = 6;

function Breakdown({ title, counts }: { title: string; counts: Record<string, number> }) {
  const { t, maybe } = useI18n();
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  if (entries.length === 0) return null;
  const total = entries.reduce((sum, [, count]) => sum + count, 0);
  return (
    <section className="flex flex-col gap-1.5">
      <h2 className="font-medium">{title}</h2>
      <ul className="flex flex-col gap-1 text-sm">
        {entries.slice(0, MAX_BREAKDOWN_ROWS).map(([label, count]) => (
          <li key={label} className="flex items-baseline justify-between gap-3">
            <span>{maybe(`marketLevels.${label}`) ?? label}</span>
            <span className="font-mono tabular-nums">{Math.round((count / total) * 100)}%</span>
          </li>
        ))}
      </ul>
      <p className="text-xs text-muted-foreground">{t('market.fromAds', { count: total })}</p>
    </section>
  );
}

function SkillList({ title, skills }: { title: string; skills: string[] }) {
  if (skills.length === 0) return null;
  return (
    <section className="flex flex-col gap-1.5">
      <h2 className="font-medium">{title}</h2>
      <ul className="flex list-disc flex-col gap-0.5 ps-5 text-sm">
        {skills.map((skill) => (
          <li key={skill}>{skill}</li>
        ))}
      </ul>
    </section>
  );
}

export default function MarketPage() {
  const i18n = useI18n();
  const { t, plural, money, date, maybe, locale } = i18n;
  const [role, setRole] = useState<ChosenRole | null>(null);
  const [region, setRegion] = useState<string>(DEFAULT_REGION);
  const [result, setResult] = useState<MarketRequirements | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!role) {
      setError(t('role.pickFirst'));
      return;
    }
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await getApi().market.requirements(role.title, region, locale));
    } catch (err) {
      setError(apiErrorText(i18n, err, 'market.lookupFailed'));
    }
    setBusy(false);
  }

  const confidence = result?.salary && {
    high: t('market.confidenceHigh'),
    medium: t('market.confidenceMedium'),
    low: t('market.confidenceLow'),
  }[result.salary.confidence];

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-3xl font-semibold tracking-tight">{t('market.title')}</h1>

      <form onSubmit={handleSubmit} className="grid gap-4 rounded-lg border bg-card p-5 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="market-role">{t('role.job')}</Label>
          <RoleCombobox id="market-role" value={role} onChange={setRole} />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="market-region">{t('role.where')}</Label>
          <RegionSelect id="market-region" value={region} onChange={setRegion} />
        </div>
        <Button type="submit" disabled={busy}>
          {busy ? t('market.lookingUp') : t('market.lookUp')}
        </Button>
      </form>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {busy && <Skeleton role="status" aria-label={t('common.loading')} className="h-48 w-full" />}

      {result && (
        <div data-testid="market-result" className="flex flex-col gap-5 rounded-lg border bg-card p-5">
          <div>
            <p className="text-lg font-medium">{result.occupationName}</p>
            <p className="text-sm text-muted-foreground">
              {[
                maybe(`regions.${result.region}`) ?? result.region,
                plural('market.ads', result.sampleSize),
                result.latestPosting && t('market.newest', { date: date(result.latestPosting) }),
              ]
                .filter(Boolean)
                .join(' · ')}
            </p>
          </div>

          {result.salary ? (
            <section className="flex flex-col gap-1">
              <h2 className="font-medium">{t('market.payTitle')}</h2>
              <p className="font-mono text-2xl font-medium tabular-nums">
                {money(result.salary.p25, result.salary.currency)} – {money(result.salary.p75, result.salary.currency)}
              </p>
              <p className="text-sm">{t('market.median', { amount: money(result.salary.median, result.salary.currency) })}</p>
              {result.salary.concentrated && <p className="text-sm">{t('results.payConcentrated')}</p>}
              <p className="text-xs text-muted-foreground">
                {confidence} {t('market.withPay', { count: result.salary.sampleSize })}
                {result.salary.region !== result.region &&
                  ` ${t('market.tooFew', { region: maybe(`regions.${result.region}`) ?? result.region })}`}
              </p>
            </section>
          ) : (
            <p>{t('market.noPay')}</p>
          )}

          <div className="grid gap-5 md:grid-cols-2">
            <SkillList title={t('market.required')} skills={result.requiredSkills} />
            <SkillList title={t('market.useful')} skills={result.preferredSkills} />
            <Breakdown title={t('market.education')} counts={result.education} />
            <Breakdown title={t('market.experience')} counts={result.experience} />
          </div>
          {result.requiredSkills.length === 0 && result.preferredSkills.length === 0 && (
            <p className="text-sm">{t('market.noSkills')}</p>
          )}

          <footer className="flex flex-col gap-1 border-t pt-3 text-xs text-muted-foreground">
            <p>{t('market.limitations')}</p>
            {result.sources.map((source) => (
              <p key={source}>{source}</p>
            ))}
          </footer>
        </div>
      )}
    </div>
  );
}
