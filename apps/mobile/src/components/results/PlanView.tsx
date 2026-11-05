import { StyleSheet, Text, View } from 'react-native';
import type { RecommendedAction, ScoreResult } from '@careerfit/shared';
import { Badge, Body, Card, Heading, Muted, Notice } from '@/components/ui';
import { useI18n, type TextKey } from '@/i18n';
import { colors, space, type } from '@/theme';

const PRIORITY: Record<RecommendedAction['priority'], TextKey> = {
  high: 'plan.priorityHigh',
  medium: 'plan.priorityMedium',
  low: 'plan.priorityLow',
};

const KIND: Record<RecommendedAction['kind'], TextKey> = {
  course: 'plan.kindCourse',
  certification: 'plan.kindCertification',
  project: 'plan.kindProject',
  experience: 'plan.kindExperience',
};

export function PlanView({ result }: { result: ScoreResult }) {
  const { t, plural, maybe } = useI18n();
  const report = result.report;
  if (!report) {
    return <Notice tone={result.reportError ? 'error' : 'info'}>{t(result.reportError ? 'results.reportFailed' : 'results.planNotReady')}</Notice>;
  }

  const stages: { title: TextKey; steps: string[] }[] = [
    { title: 'plan.days30', steps: report.plan.thirtyDays },
    { title: 'plan.days60', steps: report.plan.sixtyDays },
    { title: 'plan.days90', steps: report.plan.ninetyDays },
    { title: 'plan.later', steps: report.plan.later },
  ];

  return (
    <View style={styles.stack}>
      <Card>
        <Heading>{t('plan.stagesTitle')}</Heading>
        {stages
          .filter((stage) => stage.steps.length > 0)
          .map((stage) => (
            <View key={stage.title} style={styles.stage}>
              <Text style={[type.small, styles.stageTitle]}>{t(stage.title)}</Text>
              {stage.steps.map((step) => (
                <Body key={step}>• {step}</Body>
              ))}
            </View>
          ))}
      </Card>

      {report.actions.length > 0 && (
        <Card>
          <Heading>{t('plan.nextStepsTitle')}</Heading>
          {report.actions.map((action) => (
            <View key={action.title} style={styles.action}>
              <View style={styles.badges}>
                <Badge label={t(PRIORITY[action.priority])} tone={action.priority === 'high' ? 'partly' : 'neutral'} />
                <Badge label={t(KIND[action.kind])} />
              </View>
              <Text style={[type.body, styles.actionTitle]}>{action.title}</Text>
              <Body>{action.details}</Body>
              <Muted>{t('plan.about', { duration: plural('plan.weeks', action.effortWeeks) })}</Muted>
              <Muted>{t('plan.forGap', { gap: action.gap })}</Muted>
              {action.expectedResult && <Muted>{t('plan.endUpWith', { result: action.expectedResult })}</Muted>}
              {action.providers.length > 0 && (
                <Muted>
                  {t('plan.placesToLook', {
                    places: action.providers.map((name) => maybe(`providers.${name}`) ?? name).join(', '),
                  })}
                </Muted>
              )}
              {action.uncertain && <Muted>{t('plan.uncertain')}</Muted>}
            </View>
          ))}
        </Card>
      )}

      {report.rewrites.length > 0 && (
        <Card>
          <Heading>{t('plan.rewritesTitle')}</Heading>
          <Muted>{t('plan.rewritesNote')}</Muted>
          {report.rewrites.map((rewrite) => (
            <View key={rewrite.before} style={styles.rewrite}>
              <Text style={[type.small, styles.label]}>{t('plan.before')}</Text>
              <Body style={styles.before}>{rewrite.before}</Body>
              <Text style={[type.small, styles.label]}>{t('plan.after')}</Text>
              <Body>{rewrite.after}</Body>
            </View>
          ))}
        </Card>
      )}

      {report.gaps.length > 0 && (
        <Card>
          <Heading>{t('plan.gapsTitle')}</Heading>
          {report.gaps.map((gap) => (
            <View key={gap.title} style={styles.gap}>
              <View style={styles.row}>
                <Text style={[type.body, styles.actionTitle, styles.flex]}>{gap.title}</Text>
                <Badge label={`+${plural('results.points', gap.pointsAvailable)}`} tone="partly" />
              </View>
              <Muted>{gap.detail}</Muted>
            </View>
          ))}
        </Card>
      )}

      {report.notes.map((note) => (
        <Muted key={note}>{note}</Muted>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  stack: { gap: space.lg },
  stage: { gap: space.xs },
  stageTitle: { fontWeight: '700', color: colors.primary },
  action: {
    gap: space.xs,
    paddingTop: space.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
  },
  badges: { flexDirection: 'row', gap: space.sm, flexWrap: 'wrap' },
  actionTitle: { fontWeight: '600', color: colors.foreground },
  rewrite: { gap: 2, paddingTop: space.sm },
  label: { fontWeight: '700', color: colors.mutedForeground },
  before: { color: colors.mutedForeground },
  gap: { gap: 2, paddingTop: space.sm },
  row: { flexDirection: 'row', alignItems: 'center', gap: space.md },
  flex: { flex: 1 },
});
