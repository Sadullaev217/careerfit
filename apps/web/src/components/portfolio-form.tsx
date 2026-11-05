'use client';

import { useState, type FormEvent } from 'react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useI18n } from '@/i18n/provider';
import { getApi } from '@/lib/api';
import { apiErrorText } from '@/lib/api-error';

export function PortfolioForm({ onAdded }: { onAdded: () => void | Promise<void> }) {
  const i18n = useI18n();
  const { t } = i18n;
  const [link, setLink] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await getApi().documents.addPortfolioLink({ url: link });
      setLink('');
      await onAdded();
    } catch (err) {
      setError(apiErrorText(i18n, err, 'documents.linkFailed'));
    }
    setBusy(false);
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2">
      <Label htmlFor="portfolio-link">{t('documents.linkLabel')}</Label>
      <div className="flex flex-col gap-2 sm:flex-row">
        <Input
          id="portfolio-link"
          type="url"
          required
          placeholder="https://"
          aria-describedby="portfolio-hint"
          value={link}
          onChange={(event) => setLink(event.target.value)}
        />
        <Button type="submit" variant="outline" disabled={busy}>
          {t('documents.addLink')}
        </Button>
      </div>
      <p id="portfolio-hint" className="text-sm text-muted-foreground">
        {t('documents.linkHint')}
      </p>
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
    </form>
  );
}
