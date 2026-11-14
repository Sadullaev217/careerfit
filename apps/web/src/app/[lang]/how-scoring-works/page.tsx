import { LegalPage, legalMetadata } from '@/components/legal-page';

export async function generateMetadata({ params }: PageProps<'/[lang]/how-scoring-works'>) {
  return legalMetadata((await params).lang, 'how-scoring-works');
}

export default async function Page({ params }: PageProps<'/[lang]/how-scoring-works'>) {
  return <LegalPage lang={(await params).lang} page="how-scoring-works" />;
}
