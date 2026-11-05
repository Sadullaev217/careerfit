import { useEffect, useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import { Loading } from '@/components/ui';
import { useSession } from '@/lib/session';
import { supabase } from '@/lib/supabase';

/** Where links in confirmation and reset emails land. They carry a one-time code for this phone. */
export default function AuthCallback() {
  const params = useLocalSearchParams<{ code?: string }>();
  const { session } = useSession();
  const [next, setNext] = useState<'/' | '/reset-password' | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function finish() {
      if (!supabase || typeof params.code !== 'string') {
        router.replace({ pathname: '/login', params: { error: 'auth' } });
        return;
      }
      // A reset link signs the person in like any other link, and this event is what tells them apart.
      let isPasswordReset = false;
      const {
        data: { subscription },
      } = supabase.auth.onAuthStateChange((event) => {
        if (event === 'PASSWORD_RECOVERY') isPasswordReset = true;
      });
      const { error } = await supabase.auth.exchangeCodeForSession(params.code);
      subscription.unsubscribe();
      if (cancelled) return;
      if (error) router.replace({ pathname: '/login', params: { error: 'auth' } });
      else setNext(isPasswordReset ? '/reset-password' : '/');
    }
    void finish();
    return () => {
      cancelled = true;
    };
  }, [params.code]);

  // Signed-in screens only open once the new session has reached the rest of the app.
  useEffect(() => {
    if (next && session) router.replace(next);
  }, [next, session]);

  return <Loading />;
}
