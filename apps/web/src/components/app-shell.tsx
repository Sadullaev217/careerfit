'use client';

import { Suspense, useEffect, useState, type ReactNode } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { LogOut, Menu, Plus, Settings } from 'lucide-react';
import { LanguageSwitcher } from '@/components/language-switcher';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useI18n } from '@/i18n/provider';
import { createClient } from '@/lib/supabase/client';
import type { TextKey } from '@/i18n/translate';

const LINKS: { route: string; label: TextKey }[] = [
  { route: '/analyses', label: 'nav.history' },
  { route: '/documents', label: 'nav.documents' },
  { route: '/market', label: 'nav.market' },
];

function NavLinks({ pathname }: { pathname: string | null }) {
  const { t, path } = useI18n();

  function isCurrent(route: string) {
    const full = path(route);
    return pathname === full || Boolean(pathname?.startsWith(`${full}/`));
  }

  return LINKS.map((link) => (
    <Button
      key={link.route}
      asChild
      variant="ghost"
      className={isCurrent(link.route) ? 'bg-secondary' : undefined}
    >
      <Link href={path(link.route)} aria-current={isCurrent(link.route) ? 'page' : undefined}>
        {t(link.label)}
      </Link>
    </Button>
  ));
}

function NavLinksForThisPage() {
  return <NavLinks pathname={usePathname()} />;
}

export function AppShell({ children }: { children: ReactNode }) {
  const { t, path } = useI18n();
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    createClient()
      .auth.getUser()
      .then(({ data }) => setEmail(data.user?.email ?? null))
      .catch(() => setEmail(null));
  }, []);

  async function signOut() {
    await createClient().auth.signOut();
    router.push(path('/'));
    router.refresh();
  }

  return (
    <div className="flex min-h-full grow flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:start-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-card focus:px-3 focus:py-2"
      >
        {t('nav.skip')}
      </a>
      <header className="border-b bg-card">
        <div className="mx-auto flex w-full max-w-5xl items-center gap-2 px-4 py-2 sm:px-6">
          <Link href={path('/analyses')} className="me-2 text-lg font-semibold tracking-tight">
            CareerFit
          </Link>
          <nav aria-label={t('nav.main')} className="hidden items-center gap-1 md:flex">
            <Suspense fallback={<NavLinks pathname={null} />}>
              <NavLinksForThisPage />
            </Suspense>
          </nav>
          <div className="ms-auto flex items-center gap-1">
            <Button asChild className="hidden sm:inline-flex">
              <Link href={path('/analyses/new')}>
                <Plus aria-hidden="true" />
                {t('nav.newAnalysis')}
              </Link>
            </Button>
            <LanguageSwitcher />
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" aria-label={t('nav.menu')}>
                  <Menu aria-hidden="true" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                {email && (
                  <>
                    <p className="truncate px-2 py-1.5 text-sm text-muted-foreground">{email}</p>
                    <DropdownMenuSeparator />
                  </>
                )}
                <DropdownMenuItem asChild className="sm:hidden">
                  <Link href={path('/analyses/new')}>
                    <Plus aria-hidden="true" />
                    {t('nav.newAnalysis')}
                  </Link>
                </DropdownMenuItem>
                {LINKS.map((link) => (
                  <DropdownMenuItem key={link.route} asChild className="md:hidden">
                    <Link href={path(link.route)}>{t(link.label)}</Link>
                  </DropdownMenuItem>
                ))}
                <DropdownMenuItem asChild>
                  <Link href={path('/settings')}>
                    <Settings aria-hidden="true" />
                    {t('nav.settings')}
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onSelect={() => void signOut()}>
                  <LogOut aria-hidden="true" />
                  {t('nav.logOut')}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </header>
      <main id="main" className="mx-auto w-full max-w-5xl grow px-4 py-6 sm:px-6 sm:py-8">
        {children}
      </main>
    </div>
  );
}
