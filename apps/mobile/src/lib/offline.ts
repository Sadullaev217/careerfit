import { File, Paths } from 'expo-file-system';
import type { Analysis } from '@careerfit/shared';

// One finished result, kept in the app's private folder so it can be read without a connection.
// It's tied to the account that saved it and removed when that person logs out or deletes their account.
const FILE_NAME = 'last-result.json';

export type SavedResult = { analysis: Analysis; savedAt: string; userId: string };

function savedFile(): File {
  return new File(Paths.document, FILE_NAME);
}

export async function saveLastResult(analysis: Analysis, userId: string): Promise<void> {
  try {
    const file = savedFile();
    file.create({ overwrite: true });
    const saved: SavedResult = { analysis, savedAt: new Date().toISOString(), userId };
    await file.write(JSON.stringify(saved));
  } catch {
    // Saving for later is a convenience. The result on screen is unaffected if it fails.
  }
}

export async function loadLastResult(userId: string): Promise<SavedResult | null> {
  try {
    const file = savedFile();
    if (!file.exists) return null;
    const saved = JSON.parse(await file.text()) as SavedResult;
    return saved.userId === userId ? saved : null;
  } catch {
    return null;
  }
}

export function clearLastResult(): void {
  try {
    const file = savedFile();
    if (file.exists) file.delete();
  } catch {
    // Nothing more can be done here, and the next save overwrites it.
  }
}
