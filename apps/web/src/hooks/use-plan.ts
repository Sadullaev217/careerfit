'use client';

import { useCallback, useEffect, useState } from 'react';
import type { PlanInfo } from '@careerfit/shared';
import { getApi } from '@/lib/api';

/** The signed-in person's plan, usage and purchases. `reload` fetches it again, for after a payment. */
export function usePlan() {
  const [plan, setPlan] = useState<PlanInfo | null>(null);
  const [failed, setFailed] = useState(false);

  const reload = useCallback(async (): Promise<PlanInfo | null> => {
    try {
      const next = await getApi().account.plan();
      setPlan(next);
      setFailed(false);
      return next;
    } catch {
      setFailed(true);
      return null;
    }
  }, []);

  useEffect(() => {
    let active = true;
    getApi()
      .account.plan()
      .then((next) => {
        if (active) setPlan(next);
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => {
      active = false;
    };
  }, []);

  return { plan, failed, reload };
}

/**
 * Stripe tells the API about a payment a moment after the person comes back from checkout, so the page
 * asks a few times. Resolves true once `done` holds, false if it never does.
 */
export async function waitForPlan(
  reload: () => Promise<PlanInfo | null>,
  done: (plan: PlanInfo) => boolean,
  attempts = 15,
  intervalMs = 2000,
): Promise<boolean> {
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const plan = await reload();
    if (plan && done(plan)) return true;
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  return false;
}
