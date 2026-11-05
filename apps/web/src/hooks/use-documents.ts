'use client';

import { useCallback, useEffect, useState } from 'react';
import type { Document } from '@careerfit/shared';
import { getApi } from '@/lib/api';

const POLL_INTERVAL_MS = 2000;

function isProcessing(document: Document): boolean {
  return (
    document.status === 'pending' ||
    document.status === 'parsing' ||
    document.extractionStatus === 'pending' ||
    document.extractionStatus === 'running'
  );
}

export function useDocuments() {
  const [documents, setDocuments] = useState<Document[] | null>(null);
  const [failed, setFailed] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setDocuments(await getApi().documents.list());
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- loads data from the API on mount
    void refresh();
  }, [refresh]);

  const processing = documents?.some(isProcessing) ?? false;

  useEffect(() => {
    if (!processing) return;
    const timer = setInterval(() => void refresh(), POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [processing, refresh]);

  return { documents, failed, refresh };
}
