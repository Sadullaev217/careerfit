'use client';

import { useCallback, useEffect, useState } from 'react';
import type { ConsentStatus } from '@careerfit/shared';
import { getApi } from '@/lib/api';

/** Whether the signed-in person has accepted the current privacy policy, terms and AI processing. */
export function useConsent() {
  const [consent, setConsent] = useState<ConsentStatus | null>(null);
  const [failed, setFailed] = useState(false);

  const reload = useCallback(async () => {
    try {
      setConsent(await getApi().account.consent());
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }, []);

  useEffect(() => {
    let active = true;
    getApi()
      .account.consent()
      .then((next) => {
        if (active) setConsent(next);
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => {
      active = false;
    };
  }, []);

  return { consent, failed, reload };
}
