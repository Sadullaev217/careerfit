import { StyleSheet, Text, View } from 'react-native';
import { router } from 'expo-router';
import type { AlternativeRole, ScoreResult } from '@careerfit/shared';
import { Badge, Body, Button, Card, Muted, Notice } from '@/components/ui';
import { useI18n, type TextKey } from '@/i18n';
import { colors, space, type } from '@/theme';

const FIT: Record<AlternativeRole['fit'], { label: TextKey; tone: 'shown' | 'partly' | 'neutral' }> = {
  strong: { label: 'roles.fitStrong', tone: 'shown' },
  one_step: { label: 'roles.fitOneStep', tone: 'partly' },
  bigger_step: { label: 'roles.fitBiggerStep', tone: 'neutral' },
};

const PAY: Record<NonNullable<AlternativeRole['payComparedToTarget']>, TextKey> = {
  higher: 'roles.payHigher',
  similar: 'roles.paySimilar',
  lower: 'roles.payLower',
};

export function OtherRoles({ result, documentId }: { result: ScoreResult; documentId: string | null }) {
  const { t, money } = useI18n();
  const report = result.report;
  if (!report) {
    return <Notice tone={result.reportError ? 'error' : 'info'}>{t(result.reportError ? 'results.reportFailed' : 'results.planNotReady')}</Notice>;
  }
  if (report.alternativeRoles.length === 0) return <Body>{t('roles.empty')}</Body>;

  return (
    <View style={styles.stack}>
      {report.alternativeRoles.map((role) => (
        <Card key={role.occupationCode}>
          <View style={styles.row}>
            <Text style={[type.heading, styles.title]}>{role.occupationName}</Text>
            <Text style={styles.score}>{role.score}</Text>
          </View>
          <Badge label={t(FIT[role.fit].label)} tone={FIT[role.fit].tone} />
          <Body>{role.reason}</Body>
          {role.salary && (
            <Muted>
              {t('roles.pay', {
                low: money(role.salary.low, role.salary.currency),
                high: money(role.salary.high, role.salary.currency),
              })}
            </Muted>
          )}
          {role.payComparedToTarget && <Muted>{t(PAY[role.payComparedToTarget])}</Muted>}
          {role.mayNeedLicence && <Muted>{t('roles.licence')}</Muted>}
          <Button
            variant="secondary"
            title={t('roles.check')}
            accessibilityLabel={t('roles.checkNamed', { name: role.occupationName })}
            onPress={() =>
              router.push({
                pathname: '/new',
                params: {
                  role: role.occupationName,
                  occupationCode: role.occupationCode,
                  region: result.region,
                  ...(documentId ? { documentId } : {}),
                },
              })
            }
          />
        </Card>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  stack: { gap: space.lg },
  row: { flexDirection: 'row', alignItems: 'flex-start', gap: space.md },
  title: { flex: 1, color: colors.foreground },
  score: { fontSize: 24, fontWeight: '700', color: colors.primary, fontVariant: ['tabular-nums'] },
});
