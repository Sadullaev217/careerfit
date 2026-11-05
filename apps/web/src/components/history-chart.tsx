'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useI18n } from '@/i18n/provider';

const DEFAULT_WIDTH = 640;
const HEIGHT = 200;
const PADDING = { top: 14, right: 16, bottom: 24, left: 34 };
const GRID_VALUES = [0, 50, 100];
const POINT_RADIUS = 5;
const HIT_RADIUS = 16;

export type ChartPoint = { id: string; score: number; date: string };

/**
 * One role's score over time. One axis, one colour, and each point is a link, so the keyboard can reach it.
 * The list under the chart holds the same numbers for anyone who can't use the chart.
 *
 * It draws at the size it's given rather than scaling, which would shrink its labels to nothing on a phone.
 */
export function HistoryChart({ points, label }: { points: ChartPoint[]; label: string }) {
  const { t, path, date } = useI18n();
  const [active, setActive] = useState<string | null>(null);
  const [width, setWidth] = useState(DEFAULT_WIDTH);
  const container = useRef<HTMLElement>(null);

  useEffect(() => {
    const element = container.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.round(entry.contentRect.width)));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const innerWidth = Math.max(width - PADDING.left - PADDING.right, 1);
  const innerHeight = HEIGHT - PADDING.top - PADDING.bottom;
  const times = points.map((point) => new Date(point.date).getTime());
  const first = Math.min(...times);
  const last = Math.max(...times);
  const x = (time: number) =>
    PADDING.left + (last === first ? innerWidth / 2 : ((time - first) / (last - first)) * innerWidth);
  const y = (score: number) => PADDING.top + innerHeight * (1 - score / 100);
  const shape = points
    .map((point) => `${x(new Date(point.date).getTime())},${y(point.score)}`)
    .join(' ');
  const selected = points.find((point) => point.id === active);

  return (
    <figure ref={container} className="relative" data-testid="history-chart">
      <svg width={width} height={HEIGHT} role="group" aria-label={label} className="block max-w-full">
        {GRID_VALUES.map((value) => (
          <g key={value}>
            <line
              x1={PADDING.left}
              x2={width - PADDING.right}
              y1={y(value)}
              y2={y(value)}
              stroke="var(--border)"
            />
            <text
              x={PADDING.left - 8}
              y={y(value)}
              textAnchor="end"
              dominantBaseline="middle"
              fill="var(--muted-foreground)"
              fontSize="12"
            >
              {value}
            </text>
          </g>
        ))}
        {points.length > 1 && (
          <polyline
            points={shape}
            fill="none"
            stroke="var(--primary)"
            strokeWidth="2"
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        )}
        {points.map((point) => {
          const cx = x(new Date(point.date).getTime());
          const cy = y(point.score);
          return (
            <Link
              key={point.id}
              href={path(`/analyses/${point.id}`)}
              aria-label={t('history.pointLabel', { score: point.score, date: date(point.date) })}
              onMouseEnter={() => setActive(point.id)}
              onMouseLeave={() => setActive(null)}
              onFocus={() => setActive(point.id)}
              onBlur={() => setActive(null)}
            >
              <circle cx={cx} cy={cy} r={HIT_RADIUS} fill="transparent" />
              <circle
                cx={cx}
                cy={cy}
                r={active === point.id ? POINT_RADIUS + 2 : POINT_RADIUS}
                fill="var(--primary)"
                stroke="var(--card)"
                strokeWidth="2"
              />
            </Link>
          );
        })}
        {times.length > 0 && (
          <>
            <text
              x={last === first ? x(first) : PADDING.left}
              y={HEIGHT - 6}
              textAnchor={last === first ? 'middle' : 'start'}
              fill="var(--muted-foreground)"
              fontSize="12"
            >
              {date(new Date(first))}
            </text>
            {date(new Date(first)) !== date(new Date(last)) && (
              <text x={x(last)} y={HEIGHT - 6} textAnchor="end" fill="var(--muted-foreground)" fontSize="12">
                {date(new Date(last))}
              </text>
            )}
          </>
        )}
      </svg>
      <figcaption aria-hidden="true" className="min-h-5 text-center text-sm text-muted-foreground">
        {selected && t('history.pointLabel', { score: selected.score, date: date(selected.date) })}
      </figcaption>
    </figure>
  );
}
