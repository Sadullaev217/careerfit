import { useCallback, useEffect, useState } from 'react';
import { Alert, StyleSheet, Switch, View } from 'react-native';
import { apiErrorCode, type PlanInfo } from '@careerfit/shared';
import { Choice } from '@/components/Choice';
import { openLegalPage, useConsent } from '@/components/Consent';
import { DEMO_APP } from '@/components/Demo';
import { PlanCard } from '@/components/PlanCard';
import { Body, Button, Card, Heading, Muted, Notice, Screen } from '@/components/ui';
import { LOCALE_NAMES, LOCALES, useI18n, type Locale, type TextKey } from '@/i18n';
import { forgetDeletedAccount, signOut } from '@/lib/account';
import { api } from '@/lib/api';
import { refreshStorePlan } from '@/lib/purchases';
import { shareDataExport } from '@/lib/report';
import {
  alertsSupported,
  reportAlertsOn,
  turnOffReportAlerts,
  turnOnReportAlerts,
  type AlertsState,
} from '@/lib/push';
import { useSession } from '@/lib/session';
import { colors, space } from '@/theme';

const ALERT_PROBLEM: Partial<Record<AlertsState, TextKey>> = {
  denied: 'settings.notificationsDenied',
  unavailable: 'settings.notificationsUnavailable',
  failed: 'settings.notificationsFailed',
};

export default function SettingsScreen() {
  const { t, date, locale, setLocale } = useI18n();
  const { consent, reload: reloadConsent } = useConsent();
  const [withdrawFailed, setWithdrawFailed] = useState(false);
  const { session } = useSession();
  const [plan, setPlan] = useState<PlanInfo | null>(null);
  const [alertsOn, setAlertsOn] = useState(false);
  const [alertsProblem, setAlertsProblem] = useState<TextKey | null>(
    alertsSupported() ? null : 'settings.notificationsUnavailable',
  );
  const [switching, setSwitching] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteFailed, setDeleteFailed] = useState<'billing' | 'records' | 'other' | null>(null);
  const [exporting, setExporting] = useState(false);
  const [exportFailed, setExportFailed] = useState(false);

  const userId = session?.user.id;
  const loadPlan = useCallback(
    () =>
      api.account
        .plan()
        .then(setPlan)
        .catch(() => undefined),
    [],
  );

  useEffect(() => {
    // A store subscription can end without the API hearing about it, so it's checked before showing the plan.
    (userId ? refreshStorePlan(userId) : Promise.resolve()).finally(() => void loadPlan());
    reportAlertsOn()
      .then(setAlertsOn)
      .catch(() => undefined);
  }, [userId, loadPlan]);

  async function setAlerts(on: boolean) {
    setSwitching(true);
    setAlertsProblem(null);
    // Whatever happens, the switch must work again afterwards.
    try {
      if (on) {
        const state = await turnOnReportAlerts(locale);
        setAlertsOn(state === 'on');
        setAlertsProblem(ALERT_PROBLEM[state] ?? null);
      } else {
        await turnOffReportAlerts();
        setAlertsOn(false);
      }
    } catch {
      setAlertsProblem(ALERT_PROBLEM.failed ?? null);
    } finally {
      setSwitching(false);
    }
  }

  function changeLanguage(next: Locale) {
    setLocale(next);
    // Notifications are written in the language the phone registered with.
    if (alertsOn) void turnOnReportAlerts(next);
  }

  function confirmWithdraw() {
    Alert.alert(t('settings.withdrawConfirmTitle'), t('settings.withdrawConfirmBody'), [
      { text: t('common.cancel'), style: 'cancel' },
      {
        text: t('settings.withdrawConfirmAction'),
        style: 'destructive',
        onPress: () => {
          setWithdrawFailed(false);
          api.account
            .withdrawConsent()
            .then(reloadConsent)
            .catch(() => setWithdrawFailed(true));
        },
      },
    ]);
  }

  function confirmDelete() {
    const body = t(DEMO_APP ? 'demo.deleteConfirmBody' : 'settings.deleteConfirmBody');
    Alert.alert(t('settings.deleteConfirmTitle'), body, [
      { text: t('common.cancel'), style: 'cancel' },
      {
        text: t('settings.deleteConfirmAction'),
        style: 'destructive',
        onPress: () => void deleteAccount(),
      },
    ]);
  }

  async function exportData() {
    setExporting(true);
    setExportFailed(false);
    try {
      await shareDataExport();
    } catch {
      setExportFailed(true);
    } finally {
      setExporting(false);
    }
  }

  async function deleteAccount() {
    setDeleting(true);
    setDeleteFailed(null);
    try {
      await api.account.delete();
      await forgetDeletedAccount();
    } catch (error) {
      const code = apiErrorCode(error);
      setDeleteFailed(
        code === 'billing_unavailable'
          ? 'billing'
          : code === 'purchase_records_unavailable'
            ? 'records'
            : 'other',
      );
      setDeleting(false);
    }
  }

  return (
    <Screen>
      <Card>
        <Heading>{t('settings.account')}</Heading>
        {session?.user.email && (
          <Body>{t('settings.signedInAs', { email: session.user.email })}</Body>
        )}
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
        {consent && (
          <Body>
            {consent.accepted && consent.acceptedAt
              ? t('settings.privacyAccepted', { date: date(consent.acceptedAt) })
              : t('settings.privacyMissing')}
          </Body>
        )}
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
        <Muted>{t('settings.privacyNote')}</Muted>
        {withdrawFailed && <Notice tone="error">{t('settings.withdrawFailed')}</Notice>}
        {consent?.accepted && (
          <Button
            variant="secondary"
            title={t('settings.withdrawAction')}
            onPress={confirmWithdraw}
          />
        )}
      </Card>

      <Card>
        <Heading>{t('settings.exportTitle')}</Heading>
        <Body>{t('settings.exportBody')}</Body>
        {exportFailed && <Notice tone="error">{t('settings.exportFailed')}</Notice>}
        <Button
          variant="secondary"
          title={t('settings.exportAction')}
          busy={exporting}
          onPress={() => void exportData()}
        />
      </Card>

      <Card>
        <Heading>{t('settings.deleteTitle')}</Heading>
        <Body>{t('settings.deleteBody')}</Body>
        {deleteFailed && (
          <Notice tone="error">
            {deleteFailed === 'billing'
              ? t('settings.deleteBillingFailed')
              : deleteFailed === 'records'
                ? t('settings.deletePurchaseRecordsFailed')
                : t('settings.deleteFailed')}
          </Notice>
        )}
        <Button
          variant="destructive"
          title={t('settings.deleteAction')}
          busy={deleting}
          onPress={confirmDelete}
        />
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  links: { flexDirection: 'row', flexWrap: 'wrap', columnGap: space.md },
  row: { flexDirection: 'row', alignItems: 'center', gap: space.md },
  flex: { flex: 1, gap: space.xs },
});
