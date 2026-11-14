import { LegalPage, legalMetadata } from '@/components/legal-page';

export async function generateMetadata({ params }: PageProps<'/[lang]/terms'>) {
  return legalMetadata((await params).lang, 'terms');
}

export default async function Page({ params }: PageProps<'/[lang]/terms'>) {
  return <LegalPage lang={(await params).lang} page="terms" />;
}
