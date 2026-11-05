import { StyleSheet, Text, View } from 'react-native';
import type { JudgedSkill, ScoreResult } from '@careerfit/shared';
import { Badge, Card, Heading, Muted } from '@/components/ui';
import { useI18n, type TextKey } from '@/i18n';
import { colors, space, type } from '@/theme';

const LEVEL: Record<JudgedSkill['level'], { label: TextKey; tone: 'shown' | 'partly' | 'missing' }> = {
  yes: { label: 'skills.shown', tone: 'shown' },
  partly: { label: 'skills.partly', tone: 'partly' },
  no: { label: 'skills.notFound', tone: 'missing' },
};

function SkillList({ title, skills }: { title: string; skills: JudgedSkill[] }) {
  const { t } = useI18n();
  if (skills.length === 0) return null;
  return (
    <Card>
      <Heading>{title}</Heading>
      {skills.map((skill) => (
        <View key={skill.name} style={styles.skill}>
          <View style={styles.row}>
            <Text style={[type.body, styles.name]}>{skill.name}</Text>
            <Badge label={t(LEVEL[skill.level].label)} tone={LEVEL[skill.level].tone} />
          </View>
          {skill.evidence.length > 0 && <Muted>{t('skills.basedOn', { evidence: skill.evidence.join('; ') })}</Muted>}
        </View>
      ))}
    </Card>
  );
}

export function SkillsView({ result }: { result: ScoreResult }) {
  const { t } = useI18n();
  return (
    <View style={styles.stack}>
      <SkillList title={t('skills.required')} skills={result.requiredSkills} />
      <SkillList title={t('skills.preferred')} skills={result.preferredSkills} />
      <Muted>{t('skills.note')}</Muted>
    </View>
  );
}

const styles = StyleSheet.create({
  stack: { gap: space.lg },
  skill: {
    gap: 2,
    paddingTop: space.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
  },
  row: { flexDirection: 'row', alignItems: 'center', gap: space.md },
  name: { flex: 1, color: colors.foreground },
});
