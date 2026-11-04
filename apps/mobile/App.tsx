import { useEffect, useState } from 'react';
import { StatusBar } from 'expo-status-bar';
import { Alert, Button, StyleSheet, Text, TextInput, View } from 'react-native';
import * as Linking from 'expo-linking';
import * as WebBrowser from 'expo-web-browser';
import type { Session, SupabaseClient } from '@supabase/supabase-js';
import { createApiClient } from '@careerfit/shared';
import { supabase } from './lib/supabase';

const API_URL = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000';

function LoginScreen({ client }: { client: SupabaseClient }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [mode, setMode] = useState<'signin' | 'signup'>('signin');
  const [message, setMessage] = useState<string | null>(null);

  async function submit() {
    setMessage(null);
    if (mode === 'signin') {
      const { error } = await client.auth.signInWithPassword({ email, password });
      if (error) setMessage(error.message);
    } else {
      const { data, error } = await client.auth.signUp({ email, password });
      if (error) setMessage(error.message);
      else if (!data.session) setMessage('Check your email to confirm your account.');
    }
  }

  async function oauth(provider: 'google' | 'apple') {
    const redirectTo = Linking.createURL('auth/callback');
    const { data, error } = await client.auth.signInWithOAuth({
      provider,
      options: { redirectTo, skipBrowserRedirect: true },
    });
    if (error || !data.url) {
      setMessage(error?.message ?? 'Could not start sign-in.');
      return;
    }
    const result = await WebBrowser.openAuthSessionAsync(data.url, redirectTo);
    if (result.type !== 'success') return;
    const code = Linking.parse(result.url).queryParams?.code;
    if (typeof code !== 'string') {
      setMessage('Sign-in failed.');
      return;
    }
    const { error: exchangeError } = await client.auth.exchangeCodeForSession(code);
    if (exchangeError) setMessage(exchangeError.message);
  }

  return (
    <View style={styles.form}>
      <Text style={styles.title}>{mode === 'signin' ? 'Log in' : 'Create account'}</Text>
      <TextInput
        style={styles.input}
        placeholder="Email"
        accessibilityLabel="Email"
        autoCapitalize="none"
        autoComplete="email"
        keyboardType="email-address"
        value={email}
        onChangeText={setEmail}
      />
      <TextInput
        style={styles.input}
        placeholder="Password"
        accessibilityLabel="Password"
        secureTextEntry
        value={password}
        onChangeText={setPassword}
      />
      <Button title={mode === 'signin' ? 'Log in' : 'Sign up'} onPress={submit} />
      <Button title="Continue with Google" onPress={() => oauth('google')} />
      <Button title="Continue with Apple" onPress={() => oauth('apple')} />
      <Button
        title={mode === 'signin' ? 'Need an account? Sign up' : 'Have an account? Log in'}
        onPress={() => setMode(mode === 'signin' ? 'signup' : 'signin')}
      />
      {message && <Text accessibilityRole="alert">{message}</Text>}
    </View>
  );
}

function AccountScreen({ client, session }: { client: SupabaseClient; session: Session }) {
  async function deleteAccount() {
    const api = createApiClient(
      API_URL,
      async () => (await client.auth.getSession()).data.session?.access_token,
    );
    try {
      await api.account.delete();
      await client.auth.signOut({ scope: 'local' });
    } catch {
      Alert.alert('Could not delete your account. Please try again.');
    }
  }

  return (
    <View style={styles.form}>
      <Text style={styles.title}>CareerFit</Text>
      <Text>Signed in as {session.user.email ?? session.user.id}</Text>
      <Button title="Log out" onPress={() => client.auth.signOut()} />
      <Button
        title="Delete account"
        color="#dc2626"
        onPress={() =>
          Alert.alert('Delete account?', 'This permanently removes your account and all your data.', [
            { text: 'Cancel', style: 'cancel' },
            { text: 'Delete', style: 'destructive', onPress: deleteAccount },
          ])
        }
      />
    </View>
  );
}

export default function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [apiStatus, setApiStatus] = useState('Checking API…');

  useEffect(() => {
    createApiClient(API_URL)
      .health.check()
      .then((h) => setApiStatus(`API status: ${h.status} (v${h.version})`))
      .catch((err: unknown) =>
        setApiStatus(`API unreachable: ${err instanceof Error ? err.message : 'Unknown error'}`),
      );

    if (!supabase) return;
    supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data } = supabase.auth.onAuthStateChange((_event, next) => setSession(next));
    return () => data.subscription.unsubscribe();
  }, []);

  return (
    <View style={styles.container}>
      {!supabase && <Text>Sign-in is not configured yet.</Text>}
      {supabase && !session && <LoginScreen client={supabase} />}
      {supabase && session && <AccountScreen client={supabase} session={session} />}
      <Text>{apiStatus}</Text>
      <StatusBar style="auto" />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 16, padding: 24 },
  form: { alignSelf: 'stretch', gap: 12 },
  title: { fontSize: 28, fontWeight: '600' },
  input: { borderWidth: 1, borderColor: '#a1a1aa', borderRadius: 6, padding: 10 },
});
