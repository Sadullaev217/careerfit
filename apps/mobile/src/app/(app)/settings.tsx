import { useCallback, useEffect, useState } from 'react';
import { Alert, StyleSheet, Switch, View } from 'react-native';
import { apiErrorCode, type PlanInfo } from '@careerfit/shared';
import { Choice } from '@/components/Choice';
import { PlanCard } from '@/components/PlanCard';
import { Body, Button, Card, Heading, Muted, Notice, Screen } from '@/components/ui';
import { LOCALE_NAMES, LOCALES, useI18n, type Locale, type TextKey } from '@/i18n';
import { forgetDeletedAccount, signOut } from '@/lib/account';
import { api } from '@/lib/api';
import { refreshStorePlan } from '@/lib/purchases';
import { alertsSupported, reportAlertsOn, turnOffReportAlerts, turnOnReportAlerts, type AlertsState } from '@/lib/push';
import { useSession } from '@/lib/session';
import { colors, space } from '@/theme';

const ALERT_PROBLEM: Partial<Record<AlertsState, TextKey>> = {
  denied: 'settings.notificationsDenied',
  unavailable: 'settings.notificationsUnavailable',
  failed: 'settings.notificationsFailed',
};

export default function SettingsScreen() {
  const { t, locale, setLocale } = useI18n();
  const { session } = useSession();
  const [plan, setPlan] = useState<PlanInfo | null>(null);
  const [alertsOn, setAlertsOn] = useState(false);
  const [alertsProblem, setAlertsProblem] = useState<TextKey | null>(alertsSupported() ? null : 'settings.notificationsUnavailable');
  const [switching, setSwitching] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteFailed, setDeleteFailed] = useState<'billing' | 'other' | null>(null);

  const userId = session?.user.id;
  const loadPlan = useCallback(() => api.account.plan().then(setPlan).catch(() => undefined), []);

  useEffect(() => {
    // A store subscription can end without the API hearing about it, so it's checked before showing the plan.
    (userId ? refreshStorePlan(userId) : Promise.resolve()).finally(() => void loadPlan());
    reportAlertsOn().then(setAlertsOn).catch(() => undefined);
  }, [userId, loadPlan]);

  async function setAlerts(on: boolean) {
    setSwitching(true);
    setAlertsProblem(null);
    if (on) {
      const state = await turnOnReportAlerts(locale);
      setAlertsOn(state === 'on');
      setAlertsProblem(ALERT_PROBLEM[state] ?? null);
    } else {
      await turnOffReportAlerts();
      setAlertsOn(false);
    }
    setSwitching(false);
  }

  function changeLanguage(next: Locale) {
    setLocale(next);
    // Notifications are written in the language the phone registered with.
    if (alertsOn) void turnOnReportAlerts(next);
  }

  function confirmDelete() {
    Alert.alert(t('settings.deleteConfirmTitle'), t('settings.deleteConfirmBody'), [
      { text: t('common.cancel'), style: 'cancel' },
      { text: t('settings.deleteConfirmAction'), style: 'destructive', onPress: () => void deleteAccount() },
    ]);
  }

  async function deleteAccount() {
    setDeleting(true);
    setDeleteFailed(null);
    try {
      await api.account.delete();
      await forgetDeletedAccount();
    } catch (error) {
      setDeleteFailed(apiErrorCode(error) === 'billing_unavailable' ? 'billing' : 'other');
      setDeleting(false);
    }
  }

  return (
    <Screen>
      <Card>
        <Heading>{t('settings.account')}</Heading>
        {session?.user.email && <Body>{t('settings.signedInAs', { email: session.user.email })}</Body>}
        <Button variant="secondary" title={t('settings.logOut')} onPress={() => void signOut()} />
      </Card>

      <Card>
        <Heading>{t('settings.language')}</Heading>
        <Choice
          label={t('settings.language')}
          value={locale}
          onChange={changeLanguage}
          options={LOCALES.map((value) => ({ value, label: LOCALE_NAMES[value] }))}
        />
        <Muted>{t('settings.languageNote')}</Muted>
      </Card>

      <Card>
        <View style={styles.row}>
          <View style={styles.flex}>
            <Heading>{t('settings.notifications')}</Heading>
            <Muted>{t('settings.notificationsBody')}</Muted>
          </View>
          <Switch
            accessibilityLabel={t('settings.notifications')}
            value={alertsOn}
            disabled={switching || !alertsSupported()}
            onValueChange={(on) => void setAlerts(on)}
            trackColor={{ true: colors.primary, false: colors.border }}
            thumbColor={colors.card}
          />
        </View>
        {alertsProblem && <Muted>{t(alertsProblem)}</Muted>}
      </Card>

      <PlanCard plan={plan} userId={userId} onChanged={loadPlan} />

      <Card>
        <Heading>{t('settings.privacy')}</Heading>
        <Muted>{t('settings.privacyNote')}</Muted>
      </Card>

      <Card>
        <Heading>{t('settings.deleteTitle')}</Heading>
        <Body>{t('settings.deleteBody')}</Body>
        {deleteFailed && (
          <Notice tone="error">
            {deleteFailed === 'billing' ? t('settings.deleteBillingFailed') : t('settings.deleteFailed')}
          </Notice>
        )}
        <Button variant="destructive" title={t('settings.deleteAction')} busy={deleting} onPress={confirmDelete} />
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: space.md },
  flex: { flex: 1, gap: space.xs },
});
