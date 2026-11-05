import { useCallback, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { router, useFocusEffect } from 'expo-router';
import type { Analysis, Document } from '@careerfit/shared';
import { Badge, Body, Button, Card, Heading, Muted, Notice, Screen } from '@/components/ui';
import { useI18n } from '@/i18n';
import { api, isOffline } from '@/lib/api';
import { regionName } from '@/lib/labels';
import { loadLastResult, type SavedResult } from '@/lib/offline';
import { useSession } from '@/lib/session';
import { colors, MIN_TOUCH, space, type } from '@/theme';

export default function HistoryScreen() {
  const i18n = useI18n();
  const { t } = i18n;
  const { session } = useSession();
  const userId = session?.user.id;
  const [analyses, setAnalyses] = useState<Analysis[] | null>(null);
  const [documents, setDocuments] = useState<Document[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [saved, setSaved] = useState<SavedResult | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const [nextAnalyses, nextDocuments] = await Promise.all([api.analyses.list(), api.documents.list()]);
      setAnalyses(nextAnalyses);
      setDocuments(nextDocuments);
      setFailed(false);
      setSaved(null);
    } catch (error) {
      setFailed(true);
      setSaved(isOffline(error) && userId ? await loadLastResult(userId) : null);
    }
  }, [userId]);

  // Coming back to this tab after starting an analysis should show it.
  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load]),
  );

  async function refresh() {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }

  const hasResume = documents?.some((document) => document.type === 'resume') ?? false;

  return (
    <Screen onRefresh={() => void refresh()} refreshing={refreshing}>
      {failed && !saved && <Notice tone="error">{t('history.loadFailed')}</Notice>}
      {saved && (
        <>
          <Notice>{t('common.offline')}</Notice>
          <Card>
            <Heading>{t('history.savedTitle')}</Heading>
            <ResultRow analysis={saved.analysis} />
            <Muted>{t('results.savedOn', { date: i18n.date(saved.savedAt) })}</Muted>
          </Card>
        </>
      )}
      {analyses && documents && analyses.length === 0 && (
        <Card>
          <Heading>{hasResume ? t('history.emptyTitle') : t('history.startTitle')}</Heading>
          <Body>{hasResume ? t('history.emptyBody') : t('history.startBody')}</Body>
          <Button
            title={hasResume ? t('history.chooseJob') : t('history.addResume')}
            onPress={() => router.push(hasResume ? '/new' : '/documents')}
          />
        </Card>
      )}
      {analyses && analyses.length > 0 && (
        <Card>
          {analyses.map((analysis, index) => (
            <View key={analysis.id}>
              {index > 0 && <View style={styles.separator} />}
              <ResultRow analysis={analysis} />
            </View>
          ))}
        </Card>
      )}
    </Screen>
  );
}

function ResultRow({ analysis }: { analysis: Analysis }) {
  const i18n = useI18n();
  const { t } = i18n;
  const role = analysis.role ?? '';
  const working = analysis.status === 'pending' || analysis.status === 'processing';
  const label =
    analysis.status === 'completed' && analysis.score !== null
      ? t('history.openResult', { role, score: analysis.score })
      : role;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      onPress={() => router.push(`/analyses/${analysis.id}`)}
      style={({ pressed }) => [styles.row, pressed && styles.pressed]}
    >
      <View style={styles.flex}>
        <Text style={[type.body, styles.role]}>{role}</Text>
        <Muted>{[regionName(i18n, analysis.region), i18n.date(analysis.createdAt)].filter(Boolean).join(' · ')}</Muted>
      </View>
      {analysis.status === 'completed' && analysis.score !== null ? (
        <Text style={styles.score}>{analysis.score}</Text>
      ) : (
        <Badge label={working ? t('history.working') : t('history.failed')} tone={working ? 'neutral' : 'missing'} />
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: { minHeight: MIN_TOUCH + 12, flexDirection: 'row', alignItems: 'center', gap: space.md, paddingVertical: space.sm },
  pressed: { opacity: 0.7 },
  flex: { flex: 1 },
  role: { fontWeight: '600', color: colors.foreground },
  score: { fontSize: 26, fontWeight: '700', color: colors.primary, fontVariant: ['tabular-nums'] },
  separator: { height: StyleSheet.hairlineWidth, backgroundColor: colors.border },
});
