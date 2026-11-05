import { useState } from 'react';
import { router } from 'expo-router';
import { MIN_PASSWORD_LENGTH, NewPasswordSchema } from '@careerfit/shared';
import { Button, Field, Notice, Screen } from '@/components/ui';
import { useI18n, type TextKey } from '@/i18n';
import { signOut } from '@/lib/account';
import { supabase } from '@/lib/supabase';

/** Opened by the emailed reset link, which has already signed the person in. */
export default function ResetPasswordScreen() {
  const { t } = useI18n();
  const [password, setPassword] = useState('');
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [failure, setFailure] = useState<TextKey | null>(null);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  async function save() {
    setFailure(null);
    if (!NewPasswordSchema.safeParse(password).success) {
      setFieldError(t('login.passwordShort', { count: MIN_PASSWORD_LENGTH }));
      return;
    }
    setFieldError(null);
    if (!supabase) return;
    setBusy(true);
    const { error } = await supabase.auth.updateUser({ password });
    if (!error) setSaved(true);
    else if (error.code === 'same_password') setFailure('resetPassword.samePassword');
    else if (error.code === 'weak_password') setFailure('login.weakPassword');
    else setFailure('resetPassword.failed');
    setBusy(false);
  }

  if (saved) {
    return (
      <Screen>
        <Notice>{t('resetPassword.done')}</Notice>
        <Button title={t('resetPassword.continue')} onPress={() => router.replace('/')} />
      </Screen>
    );
  }

  return (
    <Screen>
      <Field
        label={t('resetPassword.password')}
        value={password}
        onChangeText={setPassword}
        error={fieldError}
        hint={t('login.passwordHint', { count: MIN_PASSWORD_LENGTH })}
        secureTextEntry
        autoComplete="new-password"
        textContentType="newPassword"
        returnKeyType="done"
        onSubmitEditing={() => void save()}
      />
      {failure && <Notice tone="error">{t(failure)}</Notice>}
      {failure === 'resetPassword.failed' && (
        <Button
          variant="link"
          title={t('resetPassword.newLink')}
          // Signing out returns to the log-in screen, where "Forgot your password?" sends a new link.
          onPress={() => void signOut()}
        />
      )}
      <Button title={t('resetPassword.submit')} busy={busy} onPress={() => void save()} />
    </Screen>
  );
}
