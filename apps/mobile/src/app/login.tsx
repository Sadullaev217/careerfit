import { useEffect, useRef, useState } from 'react';
import { StyleSheet, View, type TextInputInstance } from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import * as Linking from 'expo-linking';
import * as WebBrowser from 'expo-web-browser';
import { SafeAreaView } from 'react-native-safe-area-context';
import { EmailSchema, MIN_PASSWORD_LENGTH, NewPasswordSchema } from '@careerfit/shared';
import { Button, Divider, Field, Muted, Notice, Screen, Title } from '@/components/ui';
import { LOCALE_NAMES, LOCALES, useI18n, type TextKey } from '@/i18n';
import { supabase, SUPABASE_KEY, SUPABASE_URL } from '@/lib/supabase';
import { colors, space } from '@/theme';

type Mode = 'signin' | 'signup' | 'reset';
type SocialProvider = 'google' | 'apple';
const SOCIAL_PROVIDERS: SocialProvider[] = ['google', 'apple'];

const MODE_TEXT: Record<Mode, { title: TextKey; submit: TextKey; switchTo: TextKey }> = {
  signin: { title: 'login.titleSignIn', submit: 'login.submitSignIn', switchTo: 'login.switchToSignUp' },
  signup: { title: 'login.titleSignUp', submit: 'login.submitSignUp', switchTo: 'login.switchToSignIn' },
  reset: { title: 'login.titleReset', submit: 'login.submitReset', switchTo: 'login.backToSignIn' },
};

/** Failures worth explaining. Every other code keeps the general message for what was being done. */
const ERROR_TEXT: Record<string, TextKey> = {
  over_email_send_rate_limit: 'login.tooManyEmails',
  email_address_not_authorized: 'login.emailNotAllowed',
  weak_password: 'login.weakPassword',
};

// Links in emails come back to the app: careerfit://auth/callback in a build, an exp:// address in Expo Go.
const callbackUrl = () => Linking.createURL('auth/callback');

/** A sign-in method that isn't turned on for this project ends on an error page, so it isn't offered. */
function useSocialProviders(): SocialProvider[] {
  const [providers, setProviders] = useState<SocialProvider[]>([]);
  useEffect(() => {
    if (!SUPABASE_URL || !SUPABASE_KEY) return;
    let active = true;
    fetch(`${SUPABASE_URL}/auth/v1/settings`, { headers: { apikey: SUPABASE_KEY } })
      .then((response) => (response.ok ? response.json() : null))
      .then((settings: { external?: Record<string, boolean> } | null) => {
        if (active) setProviders(SOCIAL_PROVIDERS.filter((name) => settings?.external?.[name]));
      })
      // Email sign-in still works without this list.
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);
  return providers;
}

export default function LoginScreen() {
  const { t, locale, setLocale } = useI18n();
  const params = useLocalSearchParams<{ mode?: string; error?: string }>();
  const providers = useSocialProviders();
  const emailInput = useRef<TextInputInstance>(null);
  const [mode, setMode] = useState<Mode>(params.mode === 'signup' || params.mode === 'reset' ? params.mode : 'signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [emailError, setEmailError] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(
    params.error ? t('login.callbackFailed') : supabase ? null : t('login.notConfigured'),
  );
  const [notice, setNotice] = useState<string | null>(null);
  // Kept apart from the email box, so editing the box can't send the link somewhere else.
  const [awaitingConfirmation, setAwaitingConfirmation] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const address = email.trim();
  const text = MODE_TEXT[mode];

  function errorText(code: string | undefined, fallback: TextKey) {
    return t((code && ERROR_TEXT[code]) || fallback);
  }

  function clearMessages() {
    setMessage(null);
    setNotice(null);
    setAwaitingConfirmation(null);
    setEmailError(null);
    setPasswordError(null);
  }

  function changeMode(next: Mode) {
    setMode(next);
    clearMessages();
  }

  function valid(): boolean {
    const emailOk = EmailSchema.safeParse(address).success;
    setEmailError(emailOk ? null : t('login.emailInvalid'));
    let passwordOk = true;
    if (mode === 'signup') {
      passwordOk = NewPasswordSchema.safeParse(password).success;
      setPasswordError(passwordOk ? null : t('login.passwordShort', { count: MIN_PASSWORD_LENGTH }));
    } else if (mode === 'signin') {
      // Only new passwords follow the length rule. An older account may have a shorter one.
      passwordOk = password.length > 0;
      setPasswordError(passwordOk ? null : t('login.passwordMissing'));
    }
    return emailOk && passwordOk;
  }

  async function submit() {
    clearMessages();
    if (!supabase || !valid()) return;
    setBusy(true);
    if (mode === 'signin') {
      const { error } = await supabase.auth.signInWithPassword({ email: address, password });
      if (error?.code === 'email_not_confirmed') {
        setMessage(t('login.notConfirmed'));
        setAwaitingConfirmation(address);
      } else if (error) {
        setMessage(t('login.failed'));
      }
      // On success the session changes and the app moves on by itself.
    } else if (mode === 'signup') {
      const { data, error } = await supabase.auth.signUp({
        email: address,
        password,
        options: { emailRedirectTo: callbackUrl() },
      });
      if (error) setMessage(errorText(error.code, 'login.signupFailed'));
      else if (!data.session) {
        // Supabase gives this same answer for an email that already has an account, and sends
        // nothing. The notice covers both, so the form doesn't reveal who uses CareerFit.
        setNotice(t('login.checkEmail', { email: address }));
        setAwaitingConfirmation(address);
      }
    } else {
      const { error } = await supabase.auth.resetPasswordForEmail(address, { redirectTo: callbackUrl() });
      if (error) setMessage(errorText(error.code, 'login.resetFailed'));
      else setNotice(t('login.resetSent', { email: address }));
    }
    setBusy(false);
  }

  async function resendConfirmation(target: string) {
    if (!supabase) return;
    setBusy(true);
    setMessage(null);
    setNotice(null);
    const { error } = await supabase.auth.resend({
      type: 'signup',
      email: target,
      options: { emailRedirectTo: callbackUrl() },
    });
    if (error) setMessage(errorText(error.code, 'login.resendFailed'));
    else setNotice(t('login.resent', { email: target }));
    setBusy(false);
  }

  async function continueWith(provider: SocialProvider) {
    if (!supabase) return;
    const redirectTo = callbackUrl();
    const { data, error } = await supabase.auth.signInWithOAuth({
      provider,
      options: { redirectTo, skipBrowserRedirect: true },
    });
    if (error || !data.url) {
      setMessage(t('login.failed'));
      return;
    }
    const result = await WebBrowser.openAuthSessionAsync(data.url, redirectTo);
    if (result.type !== 'success') return;
    const code = Linking.parse(result.url).queryParams?.code;
    if (typeof code !== 'string') {
      setMessage(t('login.callbackFailed'));
      return;
    }
    const { error: exchangeError } = await supabase.auth.exchangeCodeForSession(code);
    if (exchangeError) setMessage(t('login.callbackFailed'));
  }

  return (
    <SafeAreaView style={styles.safe} edges={['top', 'bottom']}>
      <Screen>
        <View style={styles.languages}>
          {LOCALES.map((option) => (
            <Button
              key={option}
              variant="link"
              title={LOCALE_NAMES[option]}
              disabled={option === locale}
              onPress={() => setLocale(option)}
            />
          ))}
        </View>
        <Title>{t(text.title)}</Title>
        {mode === 'reset' && <Muted>{t('login.resetIntro')}</Muted>}
        <Field
          ref={emailInput}
          label={t('login.email')}
          testID="email-input"
          value={email}
          onChangeText={setEmail}
          error={emailError}
          autoCapitalize="none"
          autoComplete="email"
          keyboardType="email-address"
          textContentType="emailAddress"
          returnKeyType={mode === 'reset' ? 'send' : 'next'}
          onSubmitEditing={mode === 'reset' ? () => void submit() : undefined}
        />
        {mode !== 'reset' && (
          <View style={styles.passwordBlock}>
            <Field
              label={t('login.password')}
              testID="password-input"
              value={password}
              onChangeText={setPassword}
              error={passwordError}
              hint={mode === 'signup' ? t('login.passwordHint', { count: MIN_PASSWORD_LENGTH }) : undefined}
              secureTextEntry
              autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
              textContentType={mode === 'signin' ? 'password' : 'newPassword'}
              returnKeyType="go"
              onSubmitEditing={() => void submit()}
            />
            {mode === 'signin' && (
              <Button
                variant="link"
                title={t('login.forgot')}
                onPress={() => {
                  changeMode('reset');
                  emailInput.current?.focus();
                }}
              />
            )}
          </View>
        )}
        {message && <Notice tone="error">{message}</Notice>}
        {notice && <Notice>{notice}</Notice>}
        {awaitingConfirmation && (
          <Button
            variant="link"
            title={t('login.resend')}
            disabled={busy}
            onPress={() => void resendConfirmation(awaitingConfirmation)}
          />
        )}
        <Button title={t(text.submit)} busy={busy} disabled={!supabase} onPress={() => void submit()} />
        {mode !== 'reset' && providers.length > 0 && (
          <>
            <View style={styles.or}>
              <View style={styles.orLine}>
                <Divider />
              </View>
              <Muted>{t('login.or')}</Muted>
              <View style={styles.orLine}>
                <Divider />
              </View>
            </View>
            {providers.map((provider) => (
              <Button
                key={provider}
                variant="secondary"
                title={t(provider === 'google' ? 'login.google' : 'login.apple')}
                onPress={() => void continueWith(provider)}
              />
            ))}
          </>
        )}
        <Button variant="link" title={t(text.switchTo)} onPress={() => changeMode(mode === 'signin' ? 'signup' : 'signin')} />
      </Screen>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  languages: { flexDirection: 'row', justifyContent: 'flex-end', gap: space.lg },
  passwordBlock: { gap: space.xs },
  or: { flexDirection: 'row', alignItems: 'center', gap: space.md },
  orLine: { flex: 1 },
});
