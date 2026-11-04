'use client';

import { useState, type FormEvent } from 'react';
import Link from 'next/link';
import { apiErrorMessage, type MarketRequirements } from '@careerfit/shared';
import { getApi } from '@/lib/api';

const REGIONS = [
  'Canada',
  'Alberta',
  'British Columbia',
  'Manitoba',
  'New Brunswick',
  'Newfoundland and Labrador',
  'Northwest Territories',
  'Nova Scotia',
  'Nunavut',
  'Ontario',
  'Prince Edward Island',
  'Québec',
  'Saskatchewan',
  'Yukon',
];

const CONFIDENCE_LABELS: Record<string, string> = {
  high: 'Based on plenty of job ads',
  medium: 'Based on a moderate number of job ads',
  low: 'Based on few job ads, so treat it as a rough guide',
};

const inputClass = 'rounded border border-zinc-400 bg-transparent p-2';

function money(amount: number): string {
  return `$${amount.toLocaleString('en-CA')}`;
}

function Breakdown({ title, counts }: { title: string; counts: Record<string, number> }) {
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  if (entries.length === 0) return null;
  const total = entries.reduce((sum, [, count]) => sum + count, 0);
  return (
    <section className="flex flex-col gap-1">
      <h3 className="font-medium">{title}</h3>
      <ul className="list-disc pl-5 text-sm">
        {entries.slice(0, 6).map(([label, count]) => (
          <li key={label}>
            {label}: {Math.round((count / total) * 100)}%
          </li>
        ))}
      </ul>
      <p className="text-xs text-zinc-500">From the {total} ads that stated this.</p>
    </section>
  );
}

function SkillList({ title, skills }: { title: string; skills: string[] }) {
  if (skills.length === 0) return null;
  return (
    <section className="flex flex-col gap-1">
      <h3 className="font-medium">{title}</h3>
      <ul className="list-disc pl-5 text-sm">
        {skills.map((skill) => (
          <li key={skill}>{skill}</li>
        ))}
      </ul>
    </section>
  );
}

export default function MarketPage() {
  const [role, setRole] = useState('');
  const [region, setRegion] = useState('Ontario');
  const [result, setResult] = useState<MarketRequirements | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await getApi().market.requirements(role, region));
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not look up this role. Please try again.'));
    }
    setBusy(false);
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-2xl flex-col gap-6 p-6">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold">Job market lookup</h1>
        <Link className="underline" href="/documents">
          Your documents
        </Link>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <label className="flex flex-col gap-1">
          Job title
          <input
            className={inputClass}
            required
            minLength={2}
            maxLength={200}
            placeholder="For example, accountant"
            value={role}
            onChange={(e) => setRole(e.target.value)}
          />
        </label>
        <label className="flex flex-col gap-1">
          Where
          <select className={inputClass} value={region} onChange={(e) => setRegion(e.target.value)}>
            {REGIONS.map((name) => (
              <option key={name}>{name}</option>
            ))}
          </select>
        </label>
        <button
          className="rounded border border-zinc-400 p-2 font-medium disabled:opacity-50"
          type="submit"
          disabled={busy}
        >
          {busy ? 'Looking up…' : 'Look up'}
        </button>
      </form>

      {error && (
        <p role="alert" className="text-red-600">
          {error}
        </p>
      )}

      {result && (
        <div data-testid="market-result" className="flex flex-col gap-4">
          <p>
            Showing <span className="font-medium">{result.occupationName}</span> in {result.region}.
            We matched your search to the job title &ldquo;{result.matchedTitle}&rdquo;.
          </p>
          <p className="text-sm">
            {result.sampleSize} job {result.sampleSize === 1 ? 'ad' : 'ads'} found
            {result.latestPosting ? `, newest from ${result.latestPosting}` : ''}.
          </p>

          {result.salary ? (
            <section className="flex flex-col gap-1">
              <h3 className="font-medium">Typical yearly pay ({result.salary.currency})</h3>
              <p className="text-2xl font-semibold">
                {money(result.salary.p25)} to {money(result.salary.p75)}
              </p>
              <p className="text-sm">Middle of the range: {money(result.salary.median)}</p>
              <p className="text-xs text-zinc-500">
                {CONFIDENCE_LABELS[result.salary.confidence]} ({result.salary.sampleSize} with pay
                stated)
                {result.salary.region !== result.region
                  ? `. Too few ads in ${result.region}, so this shows all of ${result.salary.region}.`
                  : '.'}
              </p>
            </section>
          ) : (
            <p>No pay information found for this role.</p>
          )}

          <SkillList title="Skills usually required" skills={result.requiredSkills} />
          <SkillList title="Other useful skills" skills={result.preferredSkills} />
          {result.requiredSkills.length === 0 && result.preferredSkills.length === 0 && (
            <p className="text-sm">We don&apos;t have a reliable skill list for this occupation yet.</p>
          )}
          <Breakdown title="Education asked for" counts={result.education} />
          <Breakdown title="Experience asked for" counts={result.experience} />

          <footer className="flex flex-col gap-1 border-t border-zinc-400 pt-3 text-xs text-zinc-500">
            <p>{result.limitations}</p>
            {result.sources.map((source) => (
              <p key={source}>{source}</p>
            ))}
          </footer>
        </div>
      )}
    </main>
  );
}
