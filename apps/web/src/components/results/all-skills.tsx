'use client';

import { CheckCircle2, CircleDashed, CircleMinus } from 'lucide-react';
import type { JudgedSkill, ScoreResult } from '@careerfit/shared';
import { useI18n } from '@/i18n/provider';
import type { TextKey } from '@/i18n/translate';

const LEVELS: Record<JudgedSkill['level'], { label: TextKey; icon: typeof CheckCircle2; colour: string }> = {
  yes: { label: 'skills.shown', icon: CheckCircle2, colour: 'text-shown' },
  partly: { label: 'skills.partly', icon: CircleDashed, colour: 'text-partly' },
  no: { label: 'skills.notFound', icon: CircleMinus, colour: 'text-muted-foreground' },
};

function SkillList({ title, skills }: { title: string; skills: JudgedSkill[] }) {
  const { t } = useI18n();
  if (skills.length === 0) return null;
  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-xl font-semibold">{title}</h2>
      <ul className="flex flex-col divide-y rounded-lg border bg-card">
        {skills.map((skill) => {
          const level = LEVELS[skill.level];
          const Icon = level.icon;
          return (
            <li key={skill.name} data-testid="judged-skill" className="flex gap-3 p-3 text-sm">
              <Icon aria-hidden="true" className={`mt-0.5 size-4 shrink-0 ${level.colour}`} />
              <div className="min-w-0">
                <p>
                  <span className="inline-block font-medium first-letter:uppercase">{skill.name}</span>
                  <span className="text-muted-foreground"> · {t(level.label)}</span>
                </p>
                {skill.evidence.length > 0 && (
                  <p className="text-muted-foreground">
                    {t('skills.basedOn', { evidence: skill.evidence.join('; ') })}
                  </p>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export function AllSkills({ result }: { result: ScoreResult }) {
  const { t } = useI18n();
  return (
    <div className="flex flex-col gap-6">
      <SkillList title={t('skills.required')} skills={result.requiredSkills} />
      <SkillList title={t('skills.preferred')} skills={result.preferredSkills} />
      <p className="text-sm text-muted-foreground">{t('skills.note')}</p>
    </div>
  );
}
