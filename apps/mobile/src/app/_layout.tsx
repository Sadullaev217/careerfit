import { useEffect } from 'react';
import { router, Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import type { NotificationResponse } from 'expo-notifications';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { Loading } from '@/components/ui';
import { I18nProvider, useI18n } from '@/i18n';
import { loadNotifications } from '@/lib/notifications';
import { SessionProvider, useSession } from '@/lib/session';
import { colors } from '@/theme';

/** Shows report-ready notifications, and opens the report when one is tapped. */
function useReportNotifications(signedIn: boolean) {
  useEffect(() => {
    // A report can only be opened once its owner is signed in.
    if (!signedIn) return;
    let cancelled = false;
    let subscription: { remove: () => void } | undefined;
    void loadNotifications().then((Notifications) => {
      if (!Notifications || cancelled) return;
      // Shown even while the app is open, because a report finishing is the moment people wait for.
      Notifications.setNotificationHandler({
        handleNotification: async () => ({
          shouldShowBanner: true,
          shouldShowList: true,
          shouldPlaySound: false,
          shouldSetBadge: false,
        }),
      });
      const open = (response: NotificationResponse | null) => {
        const id = response?.notification.request.content.data?.analysisId;
        if (typeof id !== 'string') return;
        router.push(`/analyses/${id}`);
        Notifications.clearLastNotificationResponse();
      };
      open(Notifications.getLastNotificationResponse());
      subscription = Notifications.addNotificationResponseReceivedListener(open);
    });
    return () => {
      cancelled = true;
      subscription?.remove();
    };
  }, [signedIn]);
}

function Navigator() {
  const { session, loading } = useSession();
  const { t } = useI18n();
  const signedIn = Boolean(session);
  useReportNotifications(signedIn);

  if (loading) return <Loading />;

  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: colors.card },
        headerTintColor: colors.foreground,
        contentStyle: { backgroundColor: colors.background },
      }}
    >
      <Stack.Protected guard={signedIn}>
        <Stack.Screen name="(app)" options={{ headerShown: false }} />
        <Stack.Screen name="analyses/[id]" options={{ title: '' }} />
        <Stack.Screen name="reset-password" options={{ title: t('resetPassword.title') }} />
      </Stack.Protected>
      <Stack.Protected guard={!signedIn}>
        <Stack.Screen name="login" options={{ headerShown: false }} />
      </Stack.Protected>
      <Stack.Screen name="auth/callback" options={{ headerShown: false }} />
    </Stack>
  );
}

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <I18nProvider>
        <SessionProvider>
          <StatusBar style="dark" />
          <Navigator />
        </SessionProvider>
      </I18nProvider>
    </SafeAreaProvider>
  );
}
