import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { ExampleReport } from '@/components/example-report';
import { EXAMPLE_ANALYSES } from '@/content/example-analysis';
import { isLocale } from '@/i18n/config';
import { getDictionary } from '@/i18n/get-dictionary';

// A saved result, built into the page: no API, database or AI call on any request, so it costs
// nothing to serve and can't show anyone's data. The build fails if that stops being true.
export const ensureStatic = 'navigation';

export async function generateMetadata({ params }: PageProps<'/[lang]/example'>): Promise<Metadata> {
  const { lang } = await params;
  if (!isLocale(lang)) return {};
  const { example } = await getDictionary(lang);
  // The root layout adds " · CareerFit".
  return { title: example.title, description: example.description };
}

export default async function ExamplePage({ params }: PageProps<'/[lang]/example'>) {
  const { lang } = await params;
  if (!isLocale(lang)) notFound();
  return <ExampleReport analysis={EXAMPLE_ANALYSES[lang]} />;
}
