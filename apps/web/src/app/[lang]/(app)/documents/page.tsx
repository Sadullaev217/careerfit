'use client';

import { useState } from 'react';
import { ConsentGate } from '@/components/consent-gate';
import { SampleResumeButton } from '@/components/demo';
import { DocumentList } from '@/components/document-list';
import { PortfolioForm } from '@/components/portfolio-form';
import { ResumeUploader } from '@/components/resume-uploader';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useDocuments } from '@/hooks/use-documents';
import { useI18n } from '@/i18n/provider';

export default function DocumentsPage() {
  const { t } = useI18n();
  const { documents, failed, refresh } = useDocuments();
  const [type, setType] = useState<'resume' | 'cover_letter'>('resume');

  return (
    <div className="flex flex-col gap-8">
      <h1 className="text-3xl font-semibold tracking-tight">{t('documents.title')}</h1>

      <ConsentGate>
        <div className="grid gap-6 md:grid-cols-2">
          <section aria-labelledby="upload" className="flex flex-col gap-3">
            <h2 id="upload" className="text-xl font-semibold">
              {t('documents.uploadTitle')}
            </h2>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="document-type">{t('documents.typeLabel')}</Label>
              <Select value={type} onValueChange={(value) => setType(value as typeof type)}>
                <SelectTrigger id="document-type" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="resume">{t('documents.typeResume')}</SelectItem>
                  <SelectItem value="cover_letter">{t('documents.typeCoverLetter')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <ResumeUploader type={type} onUploaded={refresh} />
            <SampleResumeButton onAdded={refresh} />
          </section>

          <section aria-labelledby="portfolio" className="flex flex-col gap-3">
            <h2 id="portfolio" className="text-xl font-semibold">
              {t('documents.portfolioTitle')}
            </h2>
            <PortfolioForm onAdded={refresh} />
          </section>
        </div>
      </ConsentGate>

      <section aria-labelledby="added" className="flex flex-col gap-3">
        <h2 id="added" className="text-xl font-semibold">
          {t('documents.addedTitle')}
        </h2>
        <DocumentList documents={documents} failed={failed} onChanged={refresh} />
      </section>
    </div>
  );
}
