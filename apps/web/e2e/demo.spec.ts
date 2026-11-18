import { expect, test } from '@playwright/test';

import { accountsAvailable, createAccount, deleteAccount, type TestAccount } from './accounts';

// Runs against servers started with DEMO_MODE=true (API) and NEXT_PUBLIC_DEMO_MODE=true (web), as CI does.
const DEMO = process.env.E2E_DEMO === 'true';

test.describe('the public demo', () => {
  test.skip(!DEMO, 'servers not started in demo mode');

  test('every page says it is a demo @phone', async ({ page }) => {
    await page.goto('/en');
    await expect(page.getByText('Portfolio demo:', { exact: false })).toBeVisible();
  });

  test.describe('signed in', () => {
    test.skip(!accountsAvailable, 'no test Supabase project configured');
    let account: TestAccount;

    test.beforeAll(async () => {
      account = await createAccount();
    });

    test.afterAll(async () => {
      if (account) await deleteAccount(account.id);
    });

    test('a visitor can try the sample resume, and nothing is for sale', async ({ page }) => {
      await page.goto('/en/login');
      await page.getByLabel('Email').fill(account.email);
      await page.getByLabel('Password').fill(account.password);
      await page.getByRole('button', { name: 'Log in' }).click();
      await expect(page).toHaveURL(/\/en\/(analyses|onboarding)/);

      await page.goto('/en/documents');
      await page.getByLabel(/I have read and agree/).check();
      await page.getByLabel(/AI reads my resume/).check();
      await page.getByRole('button', { name: 'Agree and continue' }).click();

      await page.getByRole('button', { name: 'Use the sample resume' }).click();
      await expect(page.getByText('Sample resume (Alex Example).pdf')).toBeVisible();
      await expect(page.getByText('See what we found')).toBeVisible({ timeout: 90_000 });

      await page.goto('/en/pricing');
      await expect(page.getByText('nothing can be bought')).toBeVisible();
    });
  });
});
