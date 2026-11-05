'use client';

import { useEffect, useState, type FormEvent } from 'react';
import Link from 'next/link';
import {
  apiErrorMessage,
  type Analysis,
  type Document,
  type JudgedSkill,
  type ScoreResult,
} from '@careerfit/shared';
import { getApi } from '@/lib/api';

const POLL_INTERVAL_MS = 2000;

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

const ERROR_MESSAGES: Record<string, string> = {
  ai_unavailable: 'The AI is unavailable right now. Please try again in a few minutes.',
  invalid_model_output: "The AI gave an answer we couldn't use. Please try again.",
  not_enough_market_data: "We don't have enough job market information to score this role yet.",
  resume_not_found: 'This resume is no longer available.',
  timeout: 'Scoring took too long. Please try again.',
};
const GENERAL_ERROR = 'Something went wrong while scoring. Please try again.';

const CONFIDENCE_LABELS: Record<ScoreResult['confidence']['level'], string> = {
  high: 'High confidence',
  medium: 'Medium confidence',
  low: 'Low confidence',
};

const LEVEL_LABELS: Record<JudgedSkill['level'], string> = {
  yes: 'Shown',
  partly: 'Partly shown',
  no: 'Not found',
};

const inputClass = 'rounded border border-zinc-400 bg-transparent p-2';

function money(amount: number): string {
  return `$${amount.toLocaleString('en-CA')}`;
}

function SkillTable({ title, skills }: { title: string; skills: JudgedSkill[] }) {
  if (skills.length === 0) return null;
  return (
    <section className="flex flex-col gap-1">
      <h3 className="font-medium">{title}</h3>
      <ul className="flex flex-col gap-2 text-sm">
        {skills.map((skill) => (
          <li key={skill.name} data-testid="judged-skill">
            <span className="font-medium">{LEVEL_LABELS[skill.level]}:</span> {skill.name}
            {skill.evidence.length > 0 && (
              <span className="block text-xs text-zinc-500">
                Based on: {skill.evidence.join('; ')}
              </span>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

function Report({ result }: { result: ScoreResult }) {
  return (
    <div data-testid="score-report" className="flex flex-col gap-5">
      <section className="flex flex-col gap-1">
        <p>
          Your match for <span className="font-medium">{result.occupationName}</span> in{' '}
          {result.region}
        </p>
        <p className="text-4xl font-semibold" data-testid="score">
          {result.score} out of 100
        </p>
        <p className="text-sm font-medium">{CONFIDENCE_LABELS[result.confidence.level]}</p>
        <ul className="list-disc pl-5 text-sm">
          {result.confidence.reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      </section>

      <section className="flex flex-col gap-1">
        <h3 className="font-medium">Likely yearly pay for your profile</h3>
        {result.salary ? (
          <>
            <p className="text-2xl font-semibold">
              {money(result.salary.low)} to {money(result.salary.high)} {result.salary.currency}
            </p>
            <p className="text-sm">
              {result.salary.basis} The middle of the market is {money(result.salary.marketMedian)}.
            </p>
            {result.salary.concentrated && (
              <p className="text-sm">
                Most of these ads list the same pay, often from one employer or pay scale, so this
                may not reflect the wider market.
              </p>
            )}
          </>
        ) : (
          <p className="text-sm">No pay information found for this role.</p>
        )}
      </section>

      <section className="flex flex-col gap-3">
        <h3 className="font-medium">How the score adds up</h3>
        <ul className="flex flex-col gap-3">
          {result.categories.map((category) => (
            <li key={category.key} data-testid="score-category">
              <div className="flex justify-between gap-4 font-medium">
                <span>{category.label}</span>
                <span className="whitespace-nowrap">
                  {category.points} of {category.maxPoints}
                </span>
              </div>
              <p className="text-sm">{category.reason}</p>
            </li>
          ))}
        </ul>
        {result.notScored.length > 0 && (
          <div className="text-sm">
            <p className="font-medium">Left out of this score</p>
            <ul className="list-disc pl-5">
              {result.notScored.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </div>
        )}
        <p className="text-xs text-zinc-500">Points are weighted for {result.weightsUsed}.</p>
      </section>

      <SkillTable title="Required skills" skills={result.requiredSkills} />
      <SkillTable title="Other useful skills" skills={result.preferredSkills} />

      <footer className="flex flex-col gap-1 border-t border-zinc-400 pt-3 text-xs text-zinc-500">
        <p>{result.disclaimer}</p>
        <p>
          Scored on {result.asOf}
          {result.marketLatestPosting
            ? ` using job ads up to ${result.marketLatestPosting}. The score can change as new ads arrive.`
            : '.'}
        </p>
      </footer>
    </div>
  );
}

export default function AnalysisPage() {
  const [resumes, setResumes] = useState<Document[] | null>(null);
  const [documentId, setDocumentId] = useState('');
  const [role, setRole] = useState('');
  const [region, setRegion] = useState('Ontario');
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    getApi()
      .documents.list()
      .then((documents) => {
        const ready = documents.filter(
          (d) => d.type === 'resume' && d.extractionStatus === 'ready',
        );
        setResumes(ready);
        setDocumentId(ready[0]?.id ?? '');
      })
      .catch(() => setError('Could not load your resumes.'));
  }, []);

  const analysisId = analysis?.id;
  const scoring = analysis?.status === 'pending' || analysis?.status === 'processing';

  useEffect(() => {
    if (!scoring || !analysisId) return;
    const timer = setInterval(() => {
      getApi()
        .analyses.get(analysisId)
        .then(setAnalysis)
        .catch(() => setError('Could not check on your score. Please refresh the page.'));
    }, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [scoring, analysisId]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setStarting(true);
    setError(null);
    setAnalysis(null);
    try {
      const api = getApi();
      const { analysisId: id } = await api.analyses.start({ documentId, role, region });
      setAnalysis(await api.analyses.get(id));
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not start scoring. Please try again.'));
    }
    setStarting(false);
  }

  const busy = starting || scoring;
  const failure =
    analysis?.status === 'failed'
      ? (ERROR_MESSAGES[analysis.errorCode ?? ''] ?? GENERAL_ERROR)
      : null;

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-2xl flex-col gap-6 p-6">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold">Score my resume</h1>
        <Link className="underline" href="/documents">
          Your documents
        </Link>
      </div>

      {resumes?.length === 0 && (
        <p>
          You need a resume that has finished being analysed first.{' '}
          <Link className="underline" href="/documents">
            Upload one
          </Link>
          .
        </p>
      )}

      {resumes && resumes.length > 0 && (
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <label className="flex flex-col gap-1">
            Resume
            <select
              className={inputClass}
              value={documentId}
              onChange={(e) => setDocumentId(e.target.value)}
            >
              {resumes.map((resume) => (
                <option key={resume.id} value={resume.id}>
                  {resume.fileName ?? resume.id}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            Job you want
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
            <select
              className={inputClass}
              value={region}
              onChange={(e) => setRegion(e.target.value)}
            >
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
            {busy ? 'Scoring…' : 'Score my resume'}
          </button>
        </form>
      )}

      {busy && (
        <p role="status" className="text-sm">
          Comparing your resume with this job. This usually takes under a minute.
        </p>
      )}

      {(error ?? failure) && (
        <p role="alert" className="text-red-600">
          {error ?? failure}
        </p>
      )}

      {analysis?.status === 'completed' && analysis.result && <Report result={analysis.result} />}
    </main>
  );
}
