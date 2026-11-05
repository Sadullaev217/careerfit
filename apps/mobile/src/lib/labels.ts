import type { Document } from '@careerfit/shared';
import type { Translator } from '@/i18n';

export function regionName(t: Translator, region: string | null): string {
  if (!region) return '';
  return t.maybe(`regions.${region}`) ?? region;
}

export type DocumentState = { label: string; tone: 'neutral' | 'shown' | 'missing'; busy: boolean };

/** One line that says where a document is: being read, being analysed, ready, or why it failed. */
export function documentState(t: Translator, document: Document): DocumentState {
  if (document.status === 'pending' || document.status === 'parsing') {
    return { label: t.t('documents.statusReading'), tone: 'neutral', busy: true };
  }
  if (document.status === 'failed') {
    const message = document.errorCode ? t.maybe(`errors.document.${document.errorCode}`) : null;
    return { label: message ?? t.t('documents.statusFailed'), tone: 'missing', busy: false };
  }
  if (document.type === 'resume') {
    if (document.extractionStatus === 'pending' || document.extractionStatus === 'running') {
      return { label: t.t('documents.statusAnalysing'), tone: 'neutral', busy: true };
    }
    if (document.extractionStatus === 'failed') {
      const code = document.extractionErrorCode;
      const message = code ? t.maybe(`errors.extraction.${code}`) : null;
      return { label: message ?? t.t('documents.statusFailed'), tone: 'missing', busy: false };
    }
  }
  return { label: t.t('documents.statusReady'), tone: 'shown', busy: false };
}

export function isReadyResume(document: Document): boolean {
  return document.type === 'resume' && document.status === 'ready' && document.extractionStatus === 'ready';
}
