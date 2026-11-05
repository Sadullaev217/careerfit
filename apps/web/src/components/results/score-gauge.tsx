const RADIUS = 80;
const STROKE = 12;
const WIDTH = (RADIUS + STROKE) * 2;
const HEIGHT = RADIUS + STROKE * 2;
const ARC = `M ${STROKE} ${RADIUS + STROKE} A ${RADIUS} ${RADIUS} 0 0 1 ${WIDTH - STROKE} ${RADIUS + STROKE}`;

/** A half-circle meter. The number in the middle carries the value, so colour is never the only signal. */
export function ScoreGauge({
  score,
  label,
  outOfLabel,
}: {
  score: number;
  label: string;
  outOfLabel: string;
}) {
  return (
    <div className="relative mx-auto w-full max-w-64">
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label={label} className="w-full">
        <path d={ARC} fill="none" stroke="var(--secondary)" strokeWidth={STROKE} strokeLinecap="round" />
        <path
          d={ARC}
          fill="none"
          stroke="var(--primary)"
          strokeWidth={STROKE}
          strokeLinecap="round"
          pathLength={100}
          strokeDasharray={`${Math.max(score, 0.5)} 100`}
        />
      </svg>
      <div aria-hidden="true" className="absolute inset-x-0 bottom-0 flex flex-col items-center">
        <span className="font-mono text-5xl leading-none font-medium tabular-nums" data-testid="score">
          {score}
        </span>
        <span className="mt-1 text-sm text-muted-foreground">{outOfLabel}</span>
      </div>
    </div>
  );
}
