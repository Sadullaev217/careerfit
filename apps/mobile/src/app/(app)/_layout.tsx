import { Tabs } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import type { ColorValue } from 'react-native';
import { useI18n } from '@/i18n';
import { colors } from '@/theme';

type IconName = keyof typeof Ionicons.glyphMap;

function icon(name: IconName) {
  return function TabIcon({ color, size }: { color: ColorValue; size: number }) {
    return <Ionicons name={name} color={typeof color === 'string' ? color : colors.mutedForeground} size={size} />;
  };
}

export default function AppTabs() {
  const { t } = useI18n();
  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.mutedForeground,
        tabBarStyle: { backgroundColor: colors.card },
        headerStyle: { backgroundColor: colors.card },
        headerTintColor: colors.foreground,
        sceneStyle: { backgroundColor: colors.background },
      }}
    >
      <Tabs.Screen name="index" options={{ title: t('tabs.results'), tabBarIcon: icon('stats-chart-outline') }} />
      <Tabs.Screen name="new" options={{ title: t('tabs.new'), tabBarIcon: icon('add-circle-outline') }} />
      <Tabs.Screen name="documents" options={{ title: t('tabs.documents'), tabBarIcon: icon('document-text-outline') }} />
      <Tabs.Screen name="settings" options={{ title: t('tabs.settings'), tabBarIcon: icon('settings-outline') }} />
    </Tabs>
  );
}
