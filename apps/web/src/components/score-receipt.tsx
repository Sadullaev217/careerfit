import { cn } from '@/lib/utils';

export type ReceiptLine = { label: string; points: number; maxPoints: number; reason?: string };

/**
 * The signature of the app: every point in a score, listed like a statement that adds up to its total.
 * It shows what the product promises, that nothing in a score is hidden.
 */
export function ScoreReceipt({
  lines,
  total,
  totalLabel,
  ofLabel,
  className,
}: {
  lines: ReceiptLine[];
  total: number;
  totalLabel: string;
  ofLabel: (points: number, maxPoints: number) => string;
  className?: string;
}) {
  return (
    <div className={cn('font-mono text-sm', className)} data-testid="score-receipt">
      <ul className="flex flex-col">
        {lines.map((line) => (
          <li key={line.label} data-testid="receipt-line" className="border-b border-dashed py-2.5 last:border-b-0">
            <div className="flex items-baseline gap-2">
              <span className="min-w-0 font-sans font-medium">{line.label}</span>
              <span aria-hidden="true" className="mb-1 grow border-b border-dotted border-input/40" />
              <span className="whitespace-nowrap tabular-nums">{ofLabel(line.points, line.maxPoints)}</span>
            </div>
            <div
              aria-hidden="true"
              className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-secondary"
            >
              <div
                className="h-full rounded-full bg-primary"
                style={{ width: `${line.maxPoints ? (line.points / line.maxPoints) * 100 : 0}%` }}
              />
            </div>
            {line.reason && (
              <p className="mt-1.5 font-sans text-sm leading-snug text-muted-foreground">{line.reason}</p>
            )}
          </li>
        ))}
      </ul>
      <div className="mt-1 flex items-baseline justify-between gap-2 border-t-2 border-foreground pt-2.5 text-base font-medium">
        <span className="font-sans">{totalLabel}</span>
        <span className="tabular-nums" data-testid="receipt-total">
          {total}
        </span>
      </div>
    </div>
  );
}
