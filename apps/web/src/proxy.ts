import { createServerClient } from '@supabase/ssr';
import { NextResponse, type NextRequest } from 'next/server';
import { isLocale, LOCALE_COOKIE, preferredLocale } from '@/i18n/config';

const PROTECTED_ROUTES = [
  '/onboarding',
  '/documents',
  '/analyses',
  '/market',
  '/settings',
  '/pricing',
  '/reset-password',
];

export async function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const firstSegment = pathname.split('/')[1];
  const isAuthRoute = pathname.startsWith('/auth/');

  if (!isAuthRoute && !isLocale(firstSegment)) {
    const locale = preferredLocale(
      request.cookies.get(LOCALE_COOKIE)?.value,
      request.headers.get('accept-language'),
    );
    const target = `/${locale}${pathname === '/' ? '' : pathname}${search}`;
    return NextResponse.redirect(new URL(target, request.url));
  }

  let response = NextResponse.next({ request });
  const route = isAuthRoute ? pathname : pathname.slice(firstSegment.length + 1) || '/';
  const isProtected = PROTECTED_ROUTES.some(
    (path) => route === path || route.startsWith(`${path}/`),
  );
  const loginUrl = new URL(`/${firstSegment}/login`, request.url);

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
  if (!url || !key) {
    return isProtected ? NextResponse.redirect(loginUrl) : response;
  }

  const supabase = createServerClient(url, key, {
    cookies: {
      getAll: () => request.cookies.getAll(),
      setAll: (cookiesToSet, headers) => {
        cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
        response = NextResponse.next({ request });
        cookiesToSet.forEach(({ name, value, options }) =>
          response.cookies.set(name, value, options),
        );
        Object.entries(headers ?? {}).forEach(([name, value]) =>
          response.headers.set(name, value),
        );
      },
    },
  });

  const { data } = await supabase.auth.getClaims();
  if (isProtected && !data?.claims) {
    return NextResponse.redirect(loginUrl);
  }
  return response;
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|webp)$).*)'],
};
