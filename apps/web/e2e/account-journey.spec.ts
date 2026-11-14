import path from 'node:path';

import { expect, test } from '@playwright/test';

import {
  accountIsGone,
  accountsAvailable,
  createAccount,
  deleteAccount,
  type TestAccount,
} from './accounts';

const RESUME = path.join(__dirname, 'fixtures', 'made-up-resume.pdf');

test.describe('an account from sign-in to deletion', () => {
  // Needs E2E_SUPABASE_URL and E2E_SUPABASE_SECRET_KEY for a local or test project (docs/testing.md).
  test.skip(!accountsAvailable, 'no test Supabase project configured');

  let account: TestAccount;

  test.beforeAll(async () => {
    account = await createAccount();
  });

  test.afterAll(async () => {
    // Already gone when the test passed; this cleans up after a failure.
    if (account) await deleteAccount(account.id);
  });

  test('log in, agree, upload a resume, export the data and delete everything', async ({
    page,
  }) => {
    await page.goto('/en/login');
    await page.getByLabel('Email').fill(account.email);
    await page.getByLabel('Password').fill(account.password);
    await page.getByRole('button', { name: 'Log in' }).click();
    await expect(page).toHaveURL(/\/en\/(analyses|onboarding)/);

    // Nothing is read before the person agrees.
    await page.goto('/en/documents');
    const agree = page.getByRole('button', { name: 'Agree and continue' });
    await expect(agree).toBeDisabled();
    await page.getByLabel(/I have read and agree/).check();
    await page.getByLabel(/AI reads my resume/).check();
    await agree.click();

    await page.locator('input[type="file"]').first().setInputFiles(RESUME);
    await expect(page.getByText('See what we found')).toBeVisible({ timeout: 90_000 });

    await page.goto('/en/settings');
    const downloading = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Download my data' }).click();
    const download = await downloading;
    expect(download.suggestedFilename()).toMatch(/\.zip$/);

    await page.getByRole('button', { name: 'Delete my account' }).click();
    await page.getByRole('button', { name: 'Yes, delete everything' }).click();
    await expect(page).toHaveURL(/\/en\/?$/);
    expect(await accountIsGone(account.id)).toBe(true);
  });
});
