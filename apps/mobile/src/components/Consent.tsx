import { useCallback, useState, type ReactNode } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { useFocusEffect } from 'expo-router';
import * as WebBrowser from 'expo-web-browser';
import { apiErrorCode, type ConsentStatus } from '@careerfit/shared';
import { Body, Button, Card, Heading, Muted, Notice } from '@/components/ui';
import { useI18n, type Locale } from '@/i18n';
import { api, WEB_URL } from '@/lib/api';
import { colors, MIN_TOUCH, radius, space, type } from '@/theme';

export type LegalPage = 'privacy' | 'terms' | 'how-scoring-works';

/** The policy pages live on the website, in the app's language. */
export function openLegalPage(locale: Locale, page: LegalPage) {
  void WebBrowser.openBrowserAsync(`${WEB_URL}/${locale}/${page}`);
}

/** Whether the person has accepted the current agreement, read again each time the screen is shown. */
export function useConsent() {
  const [consent, setConsent] = useState<ConsentStatus | null>(null);
  const [failed, setFailed] = useState(false);

  const reload = useCallback(async () => {
    try {
      setConsent(await api.account.consent());
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      void reload();
    }, [reload]),
  );

  return { consent, failed, reload };
}

/**
 * Shows the agreement instead of `children` until it is accepted. Used where CareerFit reads a resume;
 * results, Settings and deletion never wait for it. If it can't be loaded, `children` show and the API
 * refuses uploads by itself.
 */
export function ConsentGate({ children }: { children: ReactNode }) {
  const { consent, failed, reload } = useConsent();
  if (failed || consent?.accepted) return children;
  if (!consent) return <ActivityIndicator color={colors.primary} />;
  return <ConsentCard consent={consent} onAccepted={reload} />;
}

function CheckRow({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (next: boolean) => void;
}) {
  return (
    <Pressable
      accessibilityRole="checkbox"
      accessibilityState={{ checked }}
      onPress={() => onChange(!checked)}
      style={styles.checkRow}
    >
      <View style={[styles.box, checked && styles.boxChecked]}>
        {checked && <Text style={styles.tick}>✓</Text>}
      </View>
      <Text style={[type.body, styles.checkLabel]}>{label}</Text>
    </Pressable>
  );
}

export function ConsentCard({
  consent,
  onAccepted,
}: {
  consent: ConsentStatus;
  onAccepted: () => Promise<void>;
}) {
  const { t, locale } = useI18n();
  const [agreedTerms, setAgreedTerms] = useState(false);
  const [agreedAi, setAgreedAi] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function accept() {
    setSaving(true);
    setError(null);
    try {
      await api.account.acceptConsent(consent.version);
      await onAccepted();
    } catch (err) {
      if (apiErrorCode(err) === 'consent_outdated') {
        // The policy changed while this was open: show the new version, unticked.
        setAgreedTerms(false);
        setAgreedAi(false);
        setError(t('consent.outdated'));
        await onAccepted();
      } else {
        setError(t('consent.saveFailed'));
      }
    } finally {
      setSaving(false);
    }
  }

  const points = [
    t(consent.aiProcessing === 'openrouter' ? 'consent.aiHosted' : 'consent.aiSelfHosted'),
    t('consent.personalDetails'),
    t('consent.retention'),
    t('consent.rights'),
    t('consent.estimate'),
  ];

  return (
    <Card>
      <Heading>{t('consent.title')}</Heading>
      <Body>{t('consent.intro')}</Body>
      {points.map((point) => (
        <View key={point} style={styles.point}>
          <Text style={[type.body, styles.bullet]}>•</Text>
          <Body style={styles.flex}>{point}</Body>
        </View>
      ))}
      <View style={styles.links}>
        <Button
          variant="link"
          title={t('legal.privacy')}
          onPress={() => openLegalPage(locale, 'privacy')}
        />
        <Button
          variant="link"
          title={t('legal.terms')}
          onPress={() => openLegalPage(locale, 'terms')}
        />
        <Button
          variant="link"
          title={t('legal.howScoreWorks')}
          onPress={() => openLegalPage(locale, 'how-scoring-works')}
        />
      </View>
      <CheckRow label={t('consent.agreeTerms')} checked={agreedTerms} onChange={setAgreedTerms} />
      <CheckRow label={t('consent.agreeAi')} checked={agreedAi} onChange={setAgreedAi} />
      {error && <Notice tone="error">{error}</Notice>}
      <Button
        title={t('consent.accept')}
        disabled={!agreedTerms || !agreedAi}
        busy={saving}
        onPress={() => void accept()}
      />
      <Muted>{t('consent.changeLater')}</Muted>
    </Card>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  point: { flexDirection: 'row', gap: space.sm },
  bullet: { color: colors.foreground },
  links: { flexDirection: 'row', flexWrap: 'wrap', columnGap: space.md },
  checkRow: { flexDirection: 'row', alignItems: 'center', gap: space.md, minHeight: MIN_TOUCH },
  box: {
    width: 24,
    height: 24,
    borderRadius: radius.sm,
    borderWidth: 2,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.card,
  },
  boxChecked: { borderColor: colors.primary, backgroundColor: colors.primary },
  tick: { color: colors.primaryForeground, fontWeight: '700' },
  checkLabel: { flex: 1, color: colors.foreground },
});
