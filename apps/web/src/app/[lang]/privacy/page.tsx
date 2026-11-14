import { LegalPage, legalMetadata } from '@/components/legal-page';

export async function generateMetadata({ params }: PageProps<'/[lang]/privacy'>) {
  return legalMetadata((await params).lang, 'privacy');
}

export default async function Page({ params }: PageProps<'/[lang]/privacy'>) {
  return <LegalPage lang={(await params).lang} page="privacy" />;
}
