import { useEffect, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';
import { router } from 'expo-router';
import { apiErrorCode, PRICES, type PlanInfo, type TailoredRewrite } from '@careerfit/shared';
import { Badge, Body, Button, Card, Heading, Muted, Notice } from '@/components/ui';
import { useI18n } from '@/i18n';
import { api } from '@/lib/api';
import { buyReport, purchasesAvailable } from '@/lib/purchases';
import { openReport } from '@/lib/report';
import { colors, radius, space, type } from '@/theme';

function TailoredLines({ rewrites }: { rewrites: TailoredRewrite[] }) {
  const { t } = useI18n();
  if (rewrites.length === 0) return <Muted>{t('extras.tailorEmpty')}</Muted>;
  return (
    <View style={styles.lines}>
      {rewrites.map((rewrite) => (
        <View key={rewrite.before} style={styles.line}>
          <Muted>{`${t('extras.before')}: ${rewrite.before}`}</Muted>
          {/* Selectable, so it can be copied into a resume. */}
          <Text selectable style={[type.body, styles.ink]}>
            <Text style={styles.bold}>{`${t('extras.after')}: `}</Text>
            {rewrite.after}
          </Text>
          <Badge label={t('extras.shows', { skill: rewrite.skill })} tone="shown" />
        </View>
      ))}
    </View>
  );
}

/** Under a finished result: Pro's tailored resume lines, and the detailed report bought in the store. */
export function Extras({ analysisId, userId }: { analysisId: string; userId: string | undefined }) {
  const i18n = useI18n();
  const { t, price, locale } = i18n;
  const [plan, setPlan] = useState<PlanInfo | null>(null);
  const [lines, setLines] = useState<TailoredRewrite[] | null>(null);
  const [tailoring, setTailoring] = useState(false);
  const [tailorError, setTailorError] = useState<string | null>(null);
  const [reportBusy, setReportBusy] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);

  useEffect(() => {
    api.account.plan().then(setPlan).catch(() => undefined);
    api.analyses
      .tailored(analysisId)
      .then((saved) => setLines(saved.rewrites))
      .catch(() => undefined);
  }, [analysisId]);

  const isPro = plan?.plan === 'pro';
  const bought = plan?.purchasedReports.includes(analysisId) ?? false;

  async function tailor() {
    setTailoring(true);
    setTailorError(null);
    try {
      setLines((await api.analyses.tailor(analysisId)).rewrites ?? []);
    } catch (error) {
      setTailorError(
        apiErrorCode(error) === 'nothing_to_tailor' ? t('extras.tailorNone') : i18n.errorText(error, 'extras.tailorFailed'),
      );
    }
    setTailoring(false);
  }

  async function open() {
    setReportBusy(true);
    setReportError(null);
    try {
      await openReport(analysisId, locale);
    } catch {
      setReportError(t('extras.reportFailed'));
    }
    setReportBusy(false);
  }

  async function buy() {
    if (!userId) return;
    setReportBusy(true);
    setReportError(null);
    const outcome = await buyReport(userId, analysisId);
    if (outcome === 'bought') {
      setPlan(await api.account.plan());
      setReportBusy(false);
      await open();
      return;
    }
    if (outcome !== 'cancelled') {
      setReportError(t(outcome === 'unavailable' ? 'billing.storeUnavailable' : 'billing.purchaseFailed'));
    }
    setReportBusy(false);
  }

  return (
    <View style={styles.extras}>
      <Heading>{t('extras.title')}</Heading>
      <Card>
        <View style={styles.titleRow}>
          <Heading>{t('extras.tailorTitle')}</Heading>
          <Badge label={t('extras.proBadge')} />
        </View>
        <Muted>{t('extras.tailorBody')}</Muted>
        {lines !== null ? (
          <TailoredLines rewrites={lines} />
        ) : tailoring ? (
          <View style={styles.working} accessibilityLiveRegion="polite">
            <ActivityIndicator color={colors.primary} />
            <Body style={styles.flex}>{t('extras.tailorWorking')}</Body>
          </View>
        ) : isPro ? (
          <Button title={t('extras.tailorAction')} onPress={() => void tailor()} />
        ) : (
          plan && <Button variant="secondary" title={t('billing.seePro')} onPress={() => router.push('/settings')} />
        )}
        {tailorError && <Notice tone="error">{tailorError}</Notice>}
      </Card>

      <Card>
        <Heading>{t('extras.reportTitle')}</Heading>
        <Muted>{t('extras.reportBody')}</Muted>
        {bought ? (
          <Button title={t('extras.reportOpen')} busy={reportBusy} onPress={() => void open()} />
        ) : (
          plan &&
          purchasesAvailable() && (
            <Button
              variant="secondary"
              title={t('extras.reportBuy', { price: price(PRICES.report, PRICES.currency) })}
              busy={reportBusy}
              onPress={() => void buy()}
            />
          )
        )}
        {reportError && <Notice tone="error">{reportError}</Notice>}
      </Card>
    </View>
  );
}

const styles = StyleSheet.create({
  extras: { gap: space.md },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: space.sm, flexWrap: 'wrap' },
  lines: { gap: space.sm },
  line: {
    gap: space.xs,
    padding: space.md,
    borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
  },
  bold: { fontWeight: '600' },
  ink: { color: colors.foreground },
  working: { flexDirection: 'row', alignItems: 'center', gap: space.md },
  flex: { flex: 1 },
});
