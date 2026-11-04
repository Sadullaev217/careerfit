import { useEffect, useState } from 'react';
import { StatusBar } from 'expo-status-bar';
import { StyleSheet, Text, View } from 'react-native';
import { createApiClient } from '@careerfit/shared';

// Android emulators reach the host at 10.0.2.2; physical devices need the host's LAN IP.
const api = createApiClient(process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000');

export default function App() {
  const [status, setStatus] = useState('Checking API…');

  useEffect(() => {
    api.health
      .check()
      .then((h) => setStatus(`API status: ${h.status} (v${h.version})`))
      .catch((err: unknown) =>
        setStatus(`API unreachable: ${err instanceof Error ? err.message : 'Unknown error'}`),
      );
  }, []);

  return (
    <View style={styles.container}>
      <Text style={styles.title}>CareerFit</Text>
      <Text accessibilityRole="text">{status}</Text>
      <StatusBar style="auto" />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12, padding: 24 },
  title: { fontSize: 28, fontWeight: '600' },
});
