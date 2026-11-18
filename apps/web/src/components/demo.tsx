'use client';

import { useState } from 'react';
import { FlaskConical } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { usePlan } from '@/hooks/use-plan';
import { useI18n } from '@/i18n/provider';
import { apiErrorText } from '@/lib/api-error';
import { getApi } from '@/lib/api';

/** Set on the public demo's deployment, so the banner shows before anyone signs in. */
export const DEMO_SITE = process.env.NEXT_PUBLIC_DEMO_MODE === 'true';

/** A strip above every page of the public demo: what it is and what not to upload. */
export function DemoBanner() {
  const { t } = useI18n();
  if (!DEMO_SITE) return null;
  return (
    <div
      role="note"
      className="flex items-start justify-center gap-2 border-b bg-muted px-4 py-2 text-center text-sm"
    >
      <FlaskConical aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
      <span>{t('demo.banner')}</span>
    </div>
  );
}

/** Adds the made-up sample resume, so a visitor can try the app without their own. Demo only. */
export function SampleResumeButton({ onAdded }: { onAdded: () => void | Promise<void> }) {
  const i18n = useI18n();
  const { t } = i18n;
  const { plan } = usePlan();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!plan?.demo) return null;

  async function add() {
    setBusy(true);
    setError(null);
    try {
      await getApi().documents.addSample();
      await onAdded();
    } catch (err) {
      setError(apiErrorText(i18n, err, 'demo.sampleFailed'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm text-muted-foreground">{t('demo.sampleHint')}</p>
      <Button variant="outline" className="self-start" disabled={busy} onClick={() => void add()}>
        {busy ? t('demo.sampleAdding') : t('demo.sampleAction')}
      </Button>
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
    </div>
  );
}
