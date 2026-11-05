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
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) return NextResponse.redirect(new URL(`/${locale}/analyses`, request.url));
  }
  return NextResponse.redirect(new URL(`/${locale}/login?error=auth`, request.url));
}
