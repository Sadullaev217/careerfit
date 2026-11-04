import 'react-native-url-polyfill/auto';
import { createClient } from '@supabase/supabase-js';
import { AppState } from 'react-native';
import * as SecureStore from 'expo-secure-store';

// SecureStore warns above 2048 bytes per value, and Supabase sessions can exceed that.
const CHUNK_SIZE = 1800;

const chunkedSecureStorage = {
  async getItem(key: string) {
    const count = await SecureStore.getItemAsync(`${key}.count`);
    if (!count) return null;
    const parts = await Promise.all(
      Array.from({ length: Number(count) }, (_, i) => SecureStore.getItemAsync(`${key}.${i}`)),
    );
    return parts.some((part) => part === null) ? null : parts.join('');
  },
  async removeItem(key: string) {
    const count = Number((await SecureStore.getItemAsync(`${key}.count`)) ?? 0);
    await Promise.all(
      Array.from({ length: count }, (_, i) => SecureStore.deleteItemAsync(`${key}.${i}`)),
    );
    await SecureStore.deleteItemAsync(`${key}.count`);
  },
  async setItem(key: string, value: string) {
    await chunkedSecureStorage.removeItem(key);
    const chunks = value.match(new RegExp(`[\\s\\S]{1,${CHUNK_SIZE}}`, 'g')) ?? [];
    await Promise.all(chunks.map((chunk, i) => SecureStore.setItemAsync(`${key}.${i}`, chunk)));
    await SecureStore.setItemAsync(`${key}.count`, String(chunks.length));
  },
};

const url = process.env.EXPO_PUBLIC_SUPABASE_URL;
const key = process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

export const supabase =
  url && key
    ? createClient(url, key, {
        auth: {
          storage: chunkedSecureStorage,
          autoRefreshToken: true,
          persistSession: true,
          detectSessionInUrl: false,
          flowType: 'pkce',
        },
      })
    : null;

AppState.addEventListener('change', (state) => {
  if (state === 'active') supabase?.auth.startAutoRefresh();
  else supabase?.auth.stopAutoRefresh();
});
