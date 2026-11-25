import { isRunningInExpoGo } from 'expo';
import Constants, { ExecutionEnvironment } from 'expo-constants';

type NotificationsModule = typeof import('expo-notifications');

/** Expo Go can't receive push notifications, and some Expo Go versions can't even load the module. */
// isRunningInExpoGo asks Expo Go's own native module. The execution environment alone missed Expo Go 58 on
// Android, so the app tried to set up notifications there and the call failed.
export const IN_EXPO_GO =
  isRunningInExpoGo() || Constants.executionEnvironment === ExecutionEnvironment.StoreClient;

let loading: Promise<NotificationsModule | null> | null = null;

/** The notifications module in an installed app, or null where notifications can't work. */
export function loadNotifications(): Promise<NotificationsModule | null> {
  if (IN_EXPO_GO) return Promise.resolve(null);
  loading ??= import('expo-notifications').catch(() => null);
  return loading;
}
