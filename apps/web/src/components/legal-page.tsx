import Link from 'next/link';
import { notFound } from 'next/navigation';
import { LanguageSwitcher } from '@/components/language-switcher';
import { LEGAL, type LegalPageId } from '@/content/legal';
import { isLocale } from '@/i18n/config';
import { getDictionary } from '@/i18n/get-dictionary';
import { createTranslator } from '@/i18n/translate';

const LINKS: { id: LegalPageId; label: 'legal.privacy' | 'legal.terms' | 'legal.howScoreWorks' }[] =
  [
    { id: 'privacy', label: 'legal.privacy' },
    { id: 'terms', label: 'legal.terms' },
    { id: 'how-scoring-works', label: 'legal.howScoreWorks' },
  ];

/** A public page: anyone can read the policy, the terms and how the score works, signed in or not. */
export async function LegalPage({ lang, page }: { lang: string; page: LegalPageId }) {
  if (!isLocale(lang)) notFound();
  const { t, path } = createTranslator(lang, await getDictionary(lang));
  const doc = LEGAL[page][lang];

  return (
    <div className="flex min-h-full grow flex-col">
      <header className="border-b bg-card">
        <div className="mx-auto flex w-full max-w-3xl items-center gap-2 px-4 py-2 sm:px-6">
          <Link href={path('/')} className="me-auto text-lg font-semibold tracking-tight">
            CareerFit
          </Link>
          <LanguageSwitcher />
        </div>
      </header>
      <main id="main" className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-8 sm:px-6">
        <div className="flex flex-col gap-2">
          <h1 className="text-3xl font-semibold tracking-tight">{doc.title}</h1>
          <p className="text-sm text-muted-foreground">{doc.updated}</p>
          {doc.draftNote && (
            <p className="rounded-md border border-dashed p-3 text-sm" data-testid="draft-note">
              {doc.draftNote}
            </p>
          )}
          <p className="text-lg">{doc.intro}</p>
        </div>
        {doc.sections.map((section) => (
          <section key={section.heading} className="flex flex-col gap-2">
            <h2 className="text-xl font-semibold">{section.heading}</h2>
            {section.items && (
              <ul className="flex list-disc flex-col gap-1.5 ps-5">
                {section.items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            )}
            {section.paragraphs?.map((paragraph) => (
              <p key={paragraph}>{paragraph}</p>
            ))}
          </section>
        ))}
      </main>
      <footer className="border-t">
        <nav
          aria-label={t('legal.nav')}
          className="mx-auto flex w-full max-w-3xl flex-wrap gap-x-5 gap-y-1 px-4 py-5 text-sm sm:px-6"
        >
          {LINKS.map((link) => (
            <Link
              key={link.id}
              href={path(`/${link.id}`)}
              aria-current={link.id === page ? 'page' : undefined}
              className="underline underline-offset-4"
            >
              {t(link.label)}
            </Link>
          ))}
        </nav>
      </footer>
    </div>
  );
}

export async function legalMetadata(lang: string, page: LegalPageId) {
  return { title: isLocale(lang) ? `${LEGAL[page][lang].title} · CareerFit` : 'CareerFit' };
}
