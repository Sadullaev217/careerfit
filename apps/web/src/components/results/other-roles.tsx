'use client';

import Link from 'next/link';
import { AlertTriangle } from 'lucide-react';
import type { AlternativeRole } from '@careerfit/shared';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useI18n } from '@/i18n/provider';
import type { TextKey } from '@/i18n/translate';

const FIT: Record<AlternativeRole['fit'], TextKey> = {
  strong: 'roles.fitStrong',
  one_step: 'roles.fitOneStep',
  bigger_step: 'roles.fitBiggerStep',
};
const PAY: Record<NonNullable<AlternativeRole['payComparedToTarget']>, TextKey> = {
  higher: 'roles.payHigher',
  similar: 'roles.paySimilar',
  lower: 'roles.payLower',
};

/** showRunButton is off on the public example, where starting an analysis would need an account. */
export function OtherRoles({
  roles,
  showRunButton = true,
}: {
  roles: AlternativeRole[];
  showRunButton?: boolean;
}) {
  const { t, money, path } = useI18n();
  if (roles.length === 0) {
    return <p className="text-muted-foreground">{t('roles.empty')}</p>;
  }
  return (
    <ul className="flex flex-col divide-y rounded-lg border bg-card">
      {roles.map((role) => (
        <li key={role.occupationCode} data-testid="alternative-role" className="flex flex-col gap-2 p-5">
          <div className="flex items-start justify-between gap-4">
            <div className="flex min-w-0 flex-col gap-1">
              <h2 className="font-medium">{role.occupationName}</h2>
              <Badge variant="secondary" className="self-start">
                {t(FIT[role.fit])}
              </Badge>
            </div>
            <span className="font-mono text-2xl font-medium tabular-nums" aria-label={t('results.scoreLabel', { score: role.score })}>
              {role.score}
            </span>
          </div>
          <p className="text-sm">{role.reason}</p>
          {role.salary && (
            <p className="text-sm text-muted-foreground">
              {t('roles.pay', {
                low: money(role.salary.low, role.salary.currency),
                high: money(role.salary.high, role.salary.currency),
              })}{' '}
              {role.payComparedToTarget && t(PAY[role.payComparedToTarget])}
            </p>
          )}
          {role.mayNeedLicence && (
            <p className="flex gap-1.5 text-sm font-medium text-partly">
              <AlertTriangle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
              {t('roles.licence')}
            </p>
          )}
          {showRunButton && (
            <Button asChild variant="outline" className="self-start">
              <Link
                href={path(
                  `/analyses/new?${new URLSearchParams({ role: role.occupationName, code: role.occupationCode }).toString()}`,
                )}
                aria-label={t('roles.checkNamed', { name: role.occupationName })}
              >
                {t('roles.check')}
              </Link>
            </Button>
          )}
        </li>
      ))}
    </ul>
  );
}
