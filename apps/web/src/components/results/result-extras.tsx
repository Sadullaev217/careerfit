'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { Check, Copy, Download, Loader2, Sparkles } from 'lucide-react';
import { apiErrorCode, PRICES, type TailoredRewrite } from '@careerfit/shared';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { usePlan, waitForPlan } from '@/hooks/use-plan';
import { useI18n } from '@/i18n/provider';
import { getApi } from '@/lib/api';
import { apiErrorText } from '@/lib/api-error';
import { goToCheckout } from '@/lib/billing';

function CopyButton({ text }: { text: string }) {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);
  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={() => {
        void navigator.clipboard.writeText(text).then(() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 2000);
        });
      }}
    >
      {copied ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
      {copied ? t('extras.copied') : t('extras.copy')}
    </Button>
  );
}

function TailoredLines({ rewrites }: { rewrites: TailoredRewrite[] }) {
  const { t } = useI18n();
  if (rewrites.length === 0) return <p className="text-muted-foreground">{t('extras.tailorEmpty')}</p>;
  return (
    <ol className="flex flex-col gap-3" data-testid="tailored-lines">
      {rewrites.map((rewrite) => (
        <li key={rewrite.before} className="flex flex-col gap-1 rounded-md border p-3">
          <p className="text-sm text-muted-foreground">
            <span className="font-medium">{t('extras.before')}:</span> {rewrite.before}
          </p>
          <p>
            <span className="font-medium">{t('extras.after')}:</span> {rewrite.after}
          </p>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <Badge variant="secondary">{t('extras.shows', { skill: rewrite.skill })}</Badge>
            <CopyButton text={rewrite.after} />
          </div>
        </li>
      ))}
    </ol>
  );
}

/** Pro's tailored resume lines and the one-time PDF report, under a finished result. */
export function ResultExtras({ analysisId }: { analysisId: string }) {
  const i18n = useI18n();
  const { t, price, path, locale } = i18n;
  const { plan, reload } = usePlan();
  const search = useSearchParams();
  const [lines, setLines] = useState<TailoredRewrite[] | null>(null);
  const [tailoring, setTailoring] = useState(false);
  const [tailorError, setTailorError] = useState<string | null>(null);
  const [reportBusy, setReportBusy] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);
  const [awaitingReport, setAwaitingReport] = useState(search.get('checkout') === 'report');
  const waited = useRef(false);

  useEffect(() => {
    getApi()
      .analyses.tailored(analysisId)
      .then((saved) => setLines(saved.rewrites))
      .catch(() => undefined); // the button still offers to make them
  }, [analysisId]);

  // Back from paying for the report: it unlocks once Stripe's event reaches the API.
  useEffect(() => {
    if (!awaitingReport || waited.current) return;
    waited.current = true;
    void waitForPlan(reload, (next) => next.purchasedReports.includes(analysisId)).then(() =>
      setAwaitingReport(false),
    );
  }, [awaitingReport, reload, analysisId]);

  const isPro = plan?.plan === 'pro';
  const bought = plan?.purchasedReports.includes(analysisId) ?? false;

  async function tailor() {
    setTailoring(true);
    setTailorError(null);
    try {
      setLines((await getApi().analyses.tailor(analysisId)).rewrites ?? []);
    } catch (err) {
      setTailorError(
        apiErrorCode(err) === 'nothing_to_tailor'
          ? t('extras.tailorNone')
          : apiErrorText(i18n, err, 'extras.tailorFailed'),
      );
    } finally {
      setTailoring(false);
    }
  }

  async function buyReport() {
    setReportBusy(true);
    setReportError(null);
    try {
      await goToCheckout({ kind: 'report', analysisId }, locale);
    } catch (err) {
      setReportError(apiErrorText(i18n, err, 'billing.checkoutFailed'));
      setReportBusy(false);
    }
  }

  async function downloadReport() {
    setReportBusy(true);
    setReportError(null);
    try {
      const file = await getApi().analyses.reportPdf(analysisId, locale);
      const url = URL.createObjectURL(file);
      const link = document.createElement('a');
      link.href = url;
      link.download = `careerfit-report-${analysisId.slice(0, 8)}.pdf`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setReportError(apiErrorText(i18n, err, 'extras.reportFailed'));
    } finally {
      setReportBusy(false);
    }
  }

  const card = 'flex flex-col gap-3 rounded-lg border bg-card p-5';

  return (
    <section aria-labelledby="extras-title" className="flex flex-col gap-3" data-testid="result-extras">
      <h2 id="extras-title" className="text-xl font-semibold">
        {t('extras.title')}
      </h2>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className={card} data-testid="tailor">
          <div className="flex items-center gap-2">
            <Sparkles aria-hidden="true" className="size-4 text-primary" />
            <h3 className="font-semibold">{t('extras.tailorTitle')}</h3>
            <Badge variant="secondary">{t('extras.pro')}</Badge>
          </div>
          <p className="text-sm text-muted-foreground">{t('extras.tailorBody')}</p>
          {lines !== null ? (
            <TailoredLines rewrites={lines} />
          ) : tailoring ? (
            <p role="status" className="flex items-center gap-2 text-sm">
              <Loader2 aria-hidden="true" className="size-4 animate-spin" />
              {t('extras.tailorWorking')}
            </p>
          ) : isPro ? (
            <Button className="self-start" onClick={() => void tailor()}>
              {t('extras.tailorAction')}
            </Button>
          ) : (
            plan && (
              <Button asChild variant="outline" className="self-start">
                <Link href={path('/pricing')}>{t('billing.seePlans')}</Link>
              </Button>
            )
          )}
          {tailorError && (
            <Alert variant="destructive">
              <AlertDescription>{tailorError}</AlertDescription>
            </Alert>
          )}
        </div>

        <div className={card} data-testid="report">
          <h3 className="font-semibold">{t('extras.reportTitle')}</h3>
          <p className="text-sm text-muted-foreground">{t('extras.reportBody')}</p>
          {awaitingReport && !bought ? (
            <p role="status" className="flex items-center gap-2 text-sm">
              <Loader2 aria-hidden="true" className="size-4 animate-spin" />
              {t('extras.reportWaiting')}
            </p>
          ) : bought ? (
            <Button className="self-start" disabled={reportBusy} onClick={() => void downloadReport()}>
              <Download aria-hidden="true" />
              {t('extras.reportDownload')}
            </Button>
          ) : (
            plan && (
              <Button variant="outline" className="self-start" disabled={reportBusy} onClick={() => void buyReport()}>
                {reportBusy
                  ? t('billing.opening')
                  : t('extras.reportBuy', { price: price(PRICES.report, PRICES.currency) })}
              </Button>
            )
          )}
          {reportError && (
            <Alert variant="destructive">
              <AlertDescription>{reportError}</AlertDescription>
            </Alert>
          )}
        </div>
      </div>
    </section>
  );
}
