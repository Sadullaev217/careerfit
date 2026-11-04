'use client';

import { useEffect, useState } from 'react';
import { apiErrorMessage, type DocumentAnalysis } from '@careerfit/shared';
import { getApi } from '@/lib/api';

const FLAG_LABELS: Record<string, string> = {
  work_history: 'Work history',
  work_dates: 'Work dates',
  education: 'Education',
  skills: 'Skills',
  certifications: 'Certifications',
  languages: 'Languages',
  industry: 'Industry',
  seniority: 'Seniority',
  projects: 'Projects',
};

function Section({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div className="flex flex-col gap-1">
      <h4 className="font-medium">{title}</h4>
      <ul className="list-disc pl-5">
        {items.map((item, index) => (
          <li key={`${item}-${index}`}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

function dateRange(start: string | null, end: string | null, current: boolean): string {
  const finish = current ? 'present' : end;
  if (!start && !finish) return 'dates not given';
  return `${start ?? '?'} to ${finish ?? '?'}`;
}

export function AnalysisPanel({ documentId }: { documentId: string }) {
  const [analysis, setAnalysis] = useState<DocumentAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getApi()
      .documents.analysis(documentId)
      .then(setAnalysis)
      .catch((err: unknown) => setError(apiErrorMessage(err, 'Could not load this analysis.')));
  }, [documentId]);

  if (error) {
    return (
      <p role="alert" className="text-red-600">
        {error}
      </p>
    );
  }
  if (!analysis) return <p role="status">Loading…</p>;

  const { profile, matchedSkills } = analysis;
  const matches = new Map(matchedSkills.map((m) => [m.sourceName, m.canonicalName]));
  const flagged = profile.flags.map(
    (flag) => `${FLAG_LABELS[flag.field] ?? flag.field}: ${flag.issue}`,
  );

  return (
    <div data-testid="analysis" className="flex flex-col gap-3 text-sm">
      <p className="text-zinc-500">
        Read by AI, so it can make mistakes. Skills matched to the EU&apos;s ESCO skill list show
        the standard name after the arrow.
      </p>
      <p>
        <span className="font-medium">Level:</span> {profile.seniority}
        {profile.industry_en && (
          <>
            {' · '}
            <span className="font-medium">Industry:</span> {profile.industry_en}
          </>
        )}
      </p>
      <Section
        title={`Skills (${profile.skills.length} found, ${matchedSkills.length} matched)`}
        items={profile.skills.map((skill) => {
          const match = matches.get(skill.name_en);
          return match ? `${skill.name_en} → ${match}` : `${skill.name_en} (not matched)`;
        })}
      />
      <Section
        title="Work history"
        items={profile.work_history.map(
          (job) =>
            `${job.title_en}${job.employer ? `, ${job.employer}` : ''} (${dateRange(job.start_date, job.end_date, job.is_current)})`,
        )}
      />
      <Section
        title="Education"
        items={profile.education.map((item) =>
          [item.degree, item.field_of_study, item.institution, item.end_year]
            .filter(Boolean)
            .join(', '),
        )}
      />
      <Section
        title="Certifications"
        items={profile.certifications.map((item) =>
          [item.name, item.issuer, item.year].filter(Boolean).join(', '),
        )}
      />
      <Section
        title="Languages"
        items={profile.languages.map((item) =>
          item.level ? `${item.name_en} (${item.level})` : item.name_en,
        )}
      />
      <Section title="Projects" items={profile.projects.map((item) => item.name)} />
      <Section title="Missing or unclear" items={flagged} />
    </div>
  );
}
