import Constants from 'expo-constants';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';
import { api } from './api';
import { IN_EXPO_GO, loadNotifications } from './notifications';

// The token is kept so it can be removed from the server when this person logs out.
const TOKEN_KEY = 'careerfit.pushToken';
export const REPORTS_CHANNEL = 'reports';

export type AlertsState = 'on' | 'off' | 'denied' | 'unavailable' | 'failed';

function projectId(): string | undefined {
  const fromConfig = (Constants.expoConfig?.extra as { eas?: { projectId?: string } } | undefined)?.eas?.projectId;
  return fromConfig ?? Constants.easConfig?.projectId;
}

/** Expo Go can't receive push notifications, and a build needs an Expo project to get a token. */
export function alertsSupported(): boolean {
  if (Platform.OS !== 'ios' && Platform.OS !== 'android') return false;
  return !IN_EXPO_GO && Boolean(projectId());
}

export async function reportAlertsOn(): Promise<boolean> {
  return Boolean(await SecureStore.getItemAsync(TOKEN_KEY));
}

export async function turnOnReportAlerts(language: 'en' | 'ru'): Promise<AlertsState> {
  const id = projectId();
  const Notifications = await loadNotifications();
  if (!alertsSupported() || !id || !Notifications) return 'unavailable';
  try {
    if (Platform.OS === 'android') {
      await Notifications.setNotificationChannelAsync(REPORTS_CHANNEL, {
        name: 'Reports',
        importance: Notifications.AndroidImportance.DEFAULT,
      });
    }
    const current = await Notifications.getPermissionsAsync();
    const permission = current.granted ? current : await Notifications.requestPermissionsAsync();
    if (!permission.granted) return 'denied';
    const { data: token } = await Notifications.getExpoPushTokenAsync({ projectId: id });
    await api.notifications.register({ token, platform: Platform.OS as 'ios' | 'android', language });
    await SecureStore.setItemAsync(TOKEN_KEY, token);
    return 'on';
  } catch {
    return 'failed';
  }
}

/** Best effort: the server also drops tokens that no longer reach a phone. */
export async function turnOffReportAlerts(): Promise<void> {
  const token = await SecureStore.getItemAsync(TOKEN_KEY);
  if (!token) return;
  try {
    await api.notifications.remove(token);
  } catch {
    // Signing out mustn't fail because the server couldn't be reached.
  }
  await SecureStore.deleteItemAsync(TOKEN_KEY);
}
