import { clearLastResult } from './offline';
import { turnOffReportAlerts } from './push';
import { supabase } from './supabase';

/** Everything this phone keeps about the person goes with them: alerts, the saved result, the session. */
export async function signOut(): Promise<void> {
  await turnOffReportAlerts();
  clearLastResult();
  await supabase?.auth.signOut();
}

/** After the server has deleted the account, only this phone's copies are left to remove. */
export async function forgetDeletedAccount(): Promise<void> {
  await turnOffReportAlerts();
  clearLastResult();
  // The account no longer exists, so only the local session is cleared.
  await supabase?.auth.signOut({ scope: 'local' });
}
