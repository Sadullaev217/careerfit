import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { router, useFocusEffect, useLocalSearchParams } from 'expo-router';
import {
  apiErrorCode,
  DEFAULT_REGION,
  REGIONS,
  type Document,
  type PlanInfo,
  type Region,
  type RoleSuggestion,
} from '@careerfit/shared';
import { Choice } from '@/components/Choice';
import { Body, Button, Card, Field, Heading, Muted, Notice, Screen } from '@/components/ui';
import { useI18n } from '@/i18n';
import { api } from '@/lib/api';
import { isReadyResume } from '@/lib/labels';
import { colors, MIN_TOUCH, space, type } from '@/theme';

const SEARCH_DELAY_MS = 300;
const MIN_QUERY = 2;

type Chosen = { title: string; occupationCode: string };
type Search = { state: 'idle' | 'searching' | 'done' | 'failed'; results: RoleSuggestion[] };

function isRegion(value: string | undefined): value is Region {
  return REGIONS.some((region) => region === value);
}

export default function NewAnalysisScreen() {
  const i18n = useI18n();
  const { t, locale } = i18n;
  const params = useLocalSearchParams<{ role?: string; occupationCode?: string; region?: string; documentId?: string }>();
  const [documents, setDocuments] = useState<Document[] | null>(null);
  const [documentId, setDocumentId] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [search, setSearch] = useState<Search>({ state: 'idle', results: [] });
  const [chosen, setChosen] = useState<Chosen | null>(null);
  const [region, setRegion] = useState<Region>(DEFAULT_REGION);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [plan, setPlan] = useState<PlanInfo | null>(null);
  const [limitHit, setLimitHit] = useState(false);

  // "Run a full analysis" on another role arrives here with the job already picked. This tab stays
  // mounted, so new values are applied while rendering, React's pattern for state that follows input.
  const preset = `${params.role ?? ''}|${params.occupationCode ?? ''}|${params.region ?? ''}`;
  const [appliedPreset, setAppliedPreset] = useState('||');
  if (preset !== appliedPreset) {
    setAppliedPreset(preset);
    if (params.role && params.occupationCode) {
      setChosen({ title: params.role, occupationCode: params.occupationCode });
    }
    if (isRegion(params.region)) setRegion(params.region);
  }

  const loadDocuments = useCallback(async () => {
    try {
      const next = await api.documents.list();
      setDocuments(next);
      setDocumentId((current) => {
        const ready = next.filter(isReadyResume);
        if (current && ready.some((document) => document.id === current)) return current;
        const asked = ready.find((document) => document.id === params.documentId);
        return (asked ?? ready[0])?.id ?? null;
      });
    } catch {
      setDocuments([]);
    }
  }, [params.documentId]);

  // The plan is read again on each visit: an analysis or an upgrade elsewhere changes what's left.
  const loadPlan = useCallback(() => api.account.plan().then(setPlan).catch(() => undefined), []);

  useFocusEffect(
    useCallback(() => {
      void loadDocuments();
      void loadPlan();
    }, [loadDocuments, loadPlan]),
  );

  const limit = plan?.analysesLimit ?? null;
  const usedUp = limitHit || (plan !== null && limit !== null && plan.analysesUsed >= limit);

  const text = query.trim();
  const longEnough = text.length >= MIN_QUERY;

  useEffect(() => {
    if (!longEnough) return;
    let active = true;
    const timer = setTimeout(() => {
      setSearch({ state: 'searching', results: [] });
      api.market
        .roles(text, locale)
        .then((results) => active && setSearch({ state: 'done', results }))
        .catch(() => active && setSearch({ state: 'failed', results: [] }));
    }, SEARCH_DELAY_MS);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [text, longEnough, locale]);

  // Short text shows a hint rather than stale results from a longer query.
  const shown: Search = longEnough ? search : { state: 'idle', results: [] };

  async function start() {
    setError(null);
    if (!chosen) {
      setError(t('role.pickFirst'));
      return;
    }
    if (!documentId) return;
    setStarting(true);
    try {
      const { analysisId } = await api.analyses.start({
        documentId,
        role: chosen.title,
        occupationCode: chosen.occupationCode,
        region,
        language: locale,
      });
      router.push(`/analyses/${analysisId}`);
    } catch (startError) {
      setLimitHit(apiErrorCode(startError) === 'limit_reached');
      setError(i18n.errorText(startError, 'role.startFailed'));
      void loadPlan();
    }
    setStarting(false);
  }

  const resumes = documents?.filter((document) => document.type === 'resume') ?? [];
  const ready = resumes.filter(isReadyResume);

  if (documents && ready.length === 0) {
    return (
      <Screen onRefresh={() => void loadDocuments()}>
        <Card>
          <Heading>{t('role.title')}</Heading>
          <Body>{resumes.length ? t('role.stillReading') : t('role.needResume')}</Body>
          {!resumes.length && <Button title={t('role.uploadResume')} onPress={() => router.push('/documents')} />}
        </Card>
      </Screen>
    );
  }

  return (
    <Screen>
      {!documents && <ActivityIndicator color={colors.primary} />}
      {ready.length > 1 && (
        <Card>
          <Heading>{t('role.resume')}</Heading>
          <Choice
            label={t('role.resume')}
            value={documentId}
            onChange={setDocumentId}
            options={ready.map((document) => ({ value: document.id, label: document.fileName ?? document.id }))}
          />
        </Card>
      )}

      <Card>
        <Heading>{t('role.job')}</Heading>
        {chosen ? (
          <View style={styles.chosen}>
            <Muted>{t('role.chosen')}</Muted>
            <Text style={[type.body, styles.bold]}>{chosen.title}</Text>
            <Button
              variant="link"
              title={t('role.change')}
              onPress={() => {
                setChosen(null);
                setQuery('');
              }}
            />
          </View>
        ) : (
          <>
            <Field
              label={t('role.job')}
              placeholder={t('role.searchPlaceholder')}
              value={query}
              onChangeText={setQuery}
              autoCorrect={false}
              returnKeyType="search"
            />
            <View accessibilityLiveRegion="polite">
              {shown.state === 'idle' && text.length > 0 && <Muted>{t('role.typeMore')}</Muted>}
              {shown.state === 'searching' && <Muted>{t('role.searching')}</Muted>}
              {shown.state === 'failed' && <Notice tone="error">{t('role.searchFailed')}</Notice>}
              {shown.state === 'done' && shown.results.length === 0 && <Muted>{t('role.noMatches')}</Muted>}
            </View>
            {shown.results.map((suggestion) => (
              <Pressable
                key={`${suggestion.occupationCode}-${suggestion.title}`}
                accessibilityRole="button"
                onPress={() => {
                  setChosen({ title: suggestion.title, occupationCode: suggestion.occupationCode });
                  setError(null);
                }}
                style={({ pressed }) => [styles.suggestion, pressed && styles.pressed]}
              >
                <Text style={[type.body, styles.bold]}>{suggestion.title}</Text>
                {suggestion.occupationName !== suggestion.title && <Muted>{suggestion.occupationName}</Muted>}
              </Pressable>
            ))}
          </>
        )}
      </Card>

      <Card>
        <Heading>{t('role.where')}</Heading>
        <Choice
          label={t('role.where')}
          value={region}
          onChange={setRegion}
          options={REGIONS.map((value) => ({ value, label: i18n.maybe(`regions.${value}`) ?? value }))}
        />
      </Card>

      {usedUp && plan ? (
        <Card>
          <Heading>{t('billing.limitTitle')}</Heading>
          <Body>{t('billing.limitBody', { date: i18n.date(plan.limitResetsAt) })}</Body>
          <Button variant="secondary" title={t('billing.seePro')} onPress={() => router.push('/settings')} />
        </Card>
      ) : (
        <>
          {error && <Notice tone="error">{error}</Notice>}
          {plan && limit !== null && (
            <Muted>{i18n.plural('billing.usage', limit, { count: plan.analysesUsed, limit })}</Muted>
          )}
        </>
      )}
      <Button
        title={starting ? t('role.starting') : t('role.start')}
        busy={starting}
        disabled={!documentId || usedUp}
        onPress={() => void start()}
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  chosen: { gap: space.xs },
  bold: { fontWeight: '600', color: colors.foreground },
  suggestion: {
    minHeight: MIN_TOUCH,
    justifyContent: 'center',
    paddingVertical: space.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
  },
  pressed: { opacity: 0.7 },
});
