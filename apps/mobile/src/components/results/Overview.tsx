import { StyleSheet, Text, View } from 'react-native';
import type { ScoreResult } from '@careerfit/shared';
import { Badge, Body, Card, Heading, Muted } from '@/components/ui';
import { useI18n, type TextKey } from '@/i18n';
import { colors, space, type } from '@/theme';
import { ScoreRing } from './ScoreRing';

const MAX_STRENGTHS = 6;
const MAX_TOP_GAPS = 3;
// The same bands as the web app.
const STRONG_SCORE = 65;
const MIDDLE_SCORE = 40;

const CONFIDENCE: Record<ScoreResult['confidence']['level'], TextKey> = {
  high: 'results.confidenceHigh',
  medium: 'results.confidenceMedium',
  low: 'results.confidenceLow',
};

export function Overview({ result }: { result: ScoreResult }) {
  const { t, plural, money, date } = useI18n();
  const verdict =
    result.score >= STRONG_SCORE
      ? t('results.verdictStrong')
      : result.score >= MIDDLE_SCORE
        ? t('results.verdictMiddle')
        : t('results.verdictLow');
  const strengths = result.requiredSkills.filter((skill) => skill.level === 'yes').slice(0, MAX_STRENGTHS);
  const topGaps = (result.report?.gaps ?? []).slice(0, MAX_TOP_GAPS);
  const total = result.categories.reduce((sum, category) => sum + category.points, 0);

  return (
    <View style={styles.stack}>
      <Card>
        <ScoreRing
          score={result.score}
          label={t('results.scoreLabel', { score: result.score })}
          outOf={t('results.outOf')}
        />
        <Text style={[type.heading, styles.centred]}>{verdict}</Text>
        <View style={styles.centredRow}>
          <Badge label={t(CONFIDENCE[result.confidence.level])} />
        </View>
        {result.confidence.reasons.map((reason) => (
          <Muted key={reason}>{reason}</Muted>
        ))}
        <Muted>{t('results.notProbability')}</Muted>
      </Card>

      <Card>
        <Heading>{t('results.payTitle')}</Heading>
        {result.salary ? (
          <>
            <Text style={styles.pay}>
              {money(result.salary.low, result.salary.currency)} – {money(result.salary.high, result.salary.currency)}
            </Text>
            <Muted>{t('results.payMedian', { amount: money(result.salary.marketMedian, result.salary.currency) })}</Muted>
            {result.salary.concentrated && <Muted>{t('results.payConcentrated')}</Muted>}
          </>
        ) : (
          <Body>{t('results.payNone')}</Body>
        )}
      </Card>

      <Card>
        <Heading>{t('results.strengthsTitle')}</Heading>
        {strengths.length ? (
          strengths.map((skill) => (
            <Body key={skill.name}>• {skill.name}</Body>
          ))
        ) : (
          <Body>{t('results.strengthsNone')}</Body>
        )}
      </Card>

      {topGaps.length > 0 && (
        <Card>
          <Heading>{t('results.topGapsTitle')}</Heading>
          {topGaps.map((gap) => (
            <View key={gap.title} style={styles.row}>
              <Body style={styles.flex}>{gap.title}</Body>
              <Badge label={`+${plural('results.points', gap.pointsAvailable)}`} tone="partly" />
            </View>
          ))}
        </Card>
      )}

      <Card>
        <Heading>{t('results.howTitle')}</Heading>
        {result.categories.map((category) => (
          <View key={category.key} style={styles.receiptRow}>
            <View style={styles.row}>
              <Body style={styles.flex}>{category.label}</Body>
              <Text style={styles.points}>
                {category.points}/{category.maxPoints}
              </Text>
            </View>
            <Muted>{category.reason}</Muted>
          </View>
        ))}
        <View style={[styles.row, styles.totalRow]}>
          <Text style={[type.body, styles.bold]}>{t('results.total')}</Text>
          <Text style={[styles.points, styles.bold]}>{total}/100</Text>
        </View>
        {result.notScored.length > 0 && (
          <>
            <Text style={[type.small, styles.bold]}>{t('results.leftOut')}</Text>
            {result.notScored.map((item) => (
              <Muted key={item}>• {item}</Muted>
            ))}
          </>
        )}
        <Muted>{t('results.scoredOn', { date: date(result.asOf) })}</Muted>
        <Muted>{result.disclaimer}</Muted>
      </Card>
    </View>
  );
}

const styles = StyleSheet.create({
  stack: { gap: space.lg },
  centred: { textAlign: 'center', color: colors.foreground },
  centredRow: { flexDirection: 'row', justifyContent: 'center' },
  pay: { fontSize: 24, fontWeight: '700', color: colors.foreground },
  row: { flexDirection: 'row', alignItems: 'center', gap: space.md },
  flex: { flex: 1 },
  receiptRow: { gap: 2 },
  points: { fontSize: 16, fontVariant: ['tabular-nums'], color: colors.foreground },
  bold: { fontWeight: '700', color: colors.foreground },
  totalRow: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border, paddingTop: space.sm },
});
