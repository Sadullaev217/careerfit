import { ApiError, createApiClient } from '@careerfit/shared';
import { supabase } from './supabase';

export const API_URL = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000';

export async function accessToken(): Promise<string | undefined> {
  return (await supabase?.auth.getSession())?.data.session?.access_token;
}

export const api = createApiClient(API_URL, accessToken);

/**
 * True when the server never answered. An ApiError with a status means it did answer, with an error.
 * Anything else is a failed connection: React Native 0.88 throws a plain Error for one, not a TypeError.
 */
export function isOffline(error: unknown): boolean {
  return !(error instanceof ApiError) || error.status === 0;
}
