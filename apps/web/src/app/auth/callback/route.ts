import { NextResponse, type NextRequest } from 'next/server';
import { LOCALE_COOKIE, preferredLocale } from '@/i18n/config';
import { createClient } from '@/lib/supabase/server';

export async function GET(request: NextRequest) {
  const locale = preferredLocale(
    request.cookies.get(LOCALE_COOKIE)?.value,
    request.headers.get('accept-language'),
  );
  const code = request.nextUrl.searchParams.get('code');
  if (code) {
    const supabase = await createClient();
    // A password reset link signs the person in like any other link, and this event is what tells them apart.
    let isPasswordReset = false;
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event) => {
      if (event === 'PASSWORD_RECOVERY') isPasswordReset = true;
    });
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    subscription.unsubscribe();
    if (!error) {
      const next = isPasswordReset ? 'reset-password' : 'analyses';
      return NextResponse.redirect(new URL(`/${locale}/${next}`, request.url));
    }
  }
  return NextResponse.redirect(new URL(`/${locale}/login?error=auth`, request.url));
}
