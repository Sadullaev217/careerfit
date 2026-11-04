import { createApiClient } from '@careerfit/shared';
import { createClient } from '@/lib/supabase/client';

export function getApi() {
  const supabase = createClient();
  return createApiClient(
    process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000',
    async () => (await supabase.auth.getSession()).data.session?.access_token,
  );
}
