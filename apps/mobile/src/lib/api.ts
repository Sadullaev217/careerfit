import { ApiError, createApiClient } from '@careerfit/shared';
import { supabase } from './supabase';

export const API_URL = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000';

export const api = createApiClient(
  API_URL,
  async () => (await supabase?.auth.getSession())?.data.session?.access_token,
);

/** React Native's fetch throws a TypeError when there's no connection at all. */
export function isOffline(error: unknown): boolean {
  return error instanceof TypeError || (error instanceof ApiError && error.status === 0);
}
