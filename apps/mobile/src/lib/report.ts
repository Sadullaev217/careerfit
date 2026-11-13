import { File, Paths } from 'expo-file-system';
import * as Sharing from 'expo-sharing';
import type { Locale } from '@/i18n';
import { accessToken, API_URL } from './api';

/**
 * Downloads a bought detailed report into the app's cache and opens the phone's share sheet, from where it
 * opens in a PDF viewer or goes to Files, email or a messenger. The cached copy is replaced each time.
 */
/** Downloads everything CareerFit stores about the person as a zip, then opens the share sheet. */
export async function shareDataExport(): Promise<void> {
  const token = await accessToken();
  const file = new File(Paths.cache, 'careerfit-data.zip');
  if (file.exists) file.delete();
  const saved = await File.downloadFileAsync(`${API_URL}/account/export`, file, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  await Sharing.shareAsync(saved.uri, { mimeType: 'application/zip', UTI: 'public.zip-archive' });
}

export async function openReport(analysisId: string, locale: Locale): Promise<void> {
  const token = await accessToken();
  const file = new File(Paths.cache, `careerfit-report-${analysisId.slice(0, 8)}.pdf`);
  if (file.exists) file.delete();
  const saved = await File.downloadFileAsync(
    `${API_URL}/analyses/${analysisId}/report.pdf?language=${locale}`,
    file,
    { headers: token ? { Authorization: `Bearer ${token}` } : {} },
  );
  await Sharing.shareAsync(saved.uri, { mimeType: 'application/pdf', UTI: 'com.adobe.pdf' });
}
