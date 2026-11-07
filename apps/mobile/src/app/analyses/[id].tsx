import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, StyleSheet, View } from 'react-native';
import { Stack, useFocusEffect, useLocalSearchParams } from 'expo-router';
import type { Analysis } from '@careerfit/shared';
import { Extras } from '@/components/results/Extras';
import { OtherRoles } from '@/components/results/OtherRoles';
import { Overview } from '@/components/results/Overview';
import { PlanView } from '@/components/results/PlanView';
import { SkillsView } from '@/components/results/SkillsView';
import { Body, Button, Card, Heading, Muted, Notice, Screen, Segmented } from '@/components/ui';
import { useI18n, type TextKey } from '@/i18n';
import { api, isOffline } from '@/lib/api';
import { regionName } from '@/lib/labels';
import { loadLastResult, saveLastResult } from '@/lib/offline';
import { reportAlertsOn } from '@/lib/push';
import { useSession } from '@/lib/session';
import { colors, space } from '@/theme';

const POLL_MS = 2000;
type Tab = 'overview' | 'plan' | 'roles' | 'skills';

const STAGE: Record<string, TextKey> = {
  matching: 'progress.matching',
  planning: 'progress.planning',
  alternatives: 'progress.alternatives',
};

export default function AnalysisScreen() {
  const i18n = useI18n();
  const { t } = i18n;
  const { id } = useLocalSearchParams<{ id: string }>();
  const { session } = useSession();
  const userId = session?.user.id;
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [savedOn, setSavedOn] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);
  const [failed, setFailed] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [tab, setTab] = useState<Tab>('overview');
  const [alertsOn, setAlertsOn] = useState(false);

  const load = useCallback(async () => {
    try {
      const next = await api.analyses.get(id);
      setAnalysis(next);
      setSavedOn(null);
      setOffline(false);
      setFailed(false);
      if (next.status === 'completed' && userId) await saveLastResult(next, userId);
    } catch (error) {
      // When the server can't be reached or fails, the copy saved on this phone is the next best thing.
      const saved = userId ? await loadLastResult(userId) : null;
      if (saved && saved.analysis.id === id) {
        setAnalysis(saved.analysis);
        setSavedOn(saved.savedAt);
        setOffline(isOffline(error));
      } else {
        setFailed(true);
      }
    }
  }, [id, userId]);

  // Loads on arrival, and again when coming back to this screen.
  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load]),
  );

  useEffect(() => {
    reportAlertsOn().then(setAlertsOn).catch(() => undefined);
  }, []);

  const working = analysis?.status === 'pending' || analysis?.status === 'processing';
  useEffect(() => {
    if (!working) return;
    const timer = setInterval(() => void load(), POLL_MS);
    return () => clearInterval(timer);
  }, [working, load]);

  async function refresh() {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }

  const title = analysis?.role ?? '';
  const header = <Stack.Screen options={{ title }} />;

  if (failed && !analysis) {
    return (
      <Screen onRefresh={() => void refresh()} refreshing={refreshing}>
        {header}
        <Heading>{t('results.loadFailedTitle')}</Heading>
        <Body>{t('results.loadFailed')}</Body>
        <Button title={t('common.retry')} onPress={() => void refresh()} />
      </Screen>
    );
  }

  if (!analysis) {
    return (
      <View style={styles.loading}>
        {header}
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  if (working) {
    return (
      <Screen onRefresh={() => void refresh()} refreshing={refreshing}>
        {header}
        <Card>
          <Heading>{t('progress.title')}</Heading>
          <View style={styles.progressRow} accessibilityLiveRegion="polite">
            <ActivityIndicator color={colors.primary} />
            <Body style={styles.flex}>{t(STAGE[analysis.stage ?? ''] ?? 'progress.waiting')}</Body>
          </View>
          <Muted>{t('progress.time')}</Muted>
          {alertsOn && <Muted>{t('progress.alertOn')}</Muted>}
        </Card>
      </Screen>
    );
  }

  if (analysis.status === 'failed' || !analysis.result) {
    const message = analysis.errorCode ? i18n.maybe(`errors.analysis.${analysis.errorCode}`) : null;
    return (
      <Screen onRefresh={() => void refresh()} refreshing={refreshing}>
        {header}
        <Heading>{t('results.failedTitle')}</Heading>
        <Body>{message ?? t('common.error')}</Body>
      </Screen>
    );
  }

  const result = analysis.result;
  const hasReport = Boolean(result.report);
  return (
    <Screen onRefresh={() => void refresh()} refreshing={refreshing}>
      {header}
      {savedOn && (
        <Notice>
          {`${offline ? t('common.offline') : t('results.savedCopy')} ${t('results.savedOn', { date: i18n.date(savedOn) })}`}
        </Notice>
      )}
      <Muted>{[regionName(i18n, analysis.region), i18n.date(analysis.createdAt)].filter(Boolean).join(' · ')}</Muted>
      <Segmented<Tab>
        value={tab}
        onChange={setTab}
        options={[
          { value: 'overview', label: t('results.tabOverview') },
          { value: 'plan', label: t('results.tabPlan'), disabled: !hasReport && !result.reportError },
          { value: 'roles', label: t('results.tabRoles'), disabled: !hasReport && !result.reportError },
          { value: 'skills', label: t('results.tabSkills') },
        ]}
      />
      {tab === 'overview' && <Overview result={result} />}
      {tab === 'plan' && <PlanView result={result} />}
      {tab === 'roles' && <OtherRoles result={result} documentId={analysis.documentId} />}
      {tab === 'skills' && <SkillsView result={result} />}
      {/* The copy saved for offline use can't reach the server, so it offers nothing to buy or make. */}
      {!savedOn && <Extras analysisId={analysis.id} userId={userId} />}
    </Screen>
  );
}

const styles = StyleSheet.create({
  loading: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.background },
  progressRow: { flexDirection: 'row', alignItems: 'center', gap: space.md },
  flex: { flex: 1 },
});
